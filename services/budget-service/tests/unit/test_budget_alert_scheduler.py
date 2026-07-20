"""Tests for the mid-month budget-alert scheduler sweep (F2-03).

``run_once`` drives against a real (sqlite) DB with injected ports — it covers
both the ``list_open_for_period`` sweep query and the worker logic. App imports
live in fixtures (house style): the settings singleton must not be instantiated
at collection time.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

TODAY = date(2026, 7, 18)  # mid-July → running period is 7/2026
THRESHOLDS = [80, 100]


@pytest.fixture()
async def session_factory():
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("JWT_SECRET", "test-secret")

    import app.models  # noqa: F401 — registrerer tabellerne på Base før create_all
    from app.database import Base
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture()
def ports():
    from app.application.ports.outbound import ICategoryPort, ITransactionPort

    transaction_port = AsyncMock(spec=ITransactionPort)
    category_port = AsyncMock(spec=ICategoryPort)
    category_port.get_all_names.return_value = {1: "Dagligvarer"}
    return transaction_port, category_port


async def _insert_budget(
    session_factory,
    *,
    month: int,
    year: int,
    account_id: int = 1,
    user_id: int = 1,
    amount: float = 1000.0,
    closed_at: datetime | None = None,
):
    from app.models import BudgetLineModel, MonthlyBudgetModel

    async with session_factory() as session:
        model = MonthlyBudgetModel(
            month=month,
            year=year,
            account_id=account_id,
            user_id=user_id,
            closed_at=closed_at,
            lines=[BudgetLineModel(category_id=1, amount=amount)],
        )
        session.add(model)
        await session.commit()
        return model.id


async def _count_outbox_events(session_factory) -> int:
    from app.models import OutboxEventModel
    from sqlalchemy import func, select

    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(OutboxEventModel))
        return int(result.scalar_one())


async def test_run_once_emits_event_for_line_over_threshold(session_factory, ports) -> None:
    from app.workers.budget_alert_scheduler import run_once

    await _insert_budget(session_factory, month=7, year=2026, amount=1000.0)
    ports[0].get_expenses_by_category.return_value = {1: 850.0}  # 85% → crosses 80

    counts = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])

    assert counts["budgets"] == 1
    assert counts["events"] == 1
    assert await _count_outbox_events(session_factory) == 1


async def test_run_once_only_sweeps_the_running_period(session_factory, ports) -> None:
    from app.workers.budget_alert_scheduler import run_once

    # A past-month budget (6/2026) must NOT be swept by the mid-month sweep.
    await _insert_budget(session_factory, month=6, year=2026, account_id=2, amount=1000.0)
    ports[0].get_expenses_by_category.return_value = {1: 999.0}

    counts = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])

    assert counts["budgets"] == 0
    assert counts["events"] == 0
    assert await _count_outbox_events(session_factory) == 0


async def test_run_once_skips_closed_budget(session_factory, ports) -> None:
    from app.workers.budget_alert_scheduler import run_once

    await _insert_budget(
        session_factory, month=7, year=2026, amount=1000.0, closed_at=datetime(2026, 7, 10, 12, 0)
    )
    ports[0].get_expenses_by_category.return_value = {1: 900.0}

    counts = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])

    assert counts["budgets"] == 0
    assert await _count_outbox_events(session_factory) == 0


async def test_run_once_over_budget_emits_both_thresholds(session_factory, ports) -> None:
    from app.workers.budget_alert_scheduler import run_once

    await _insert_budget(session_factory, month=7, year=2026, amount=1000.0)
    ports[0].get_expenses_by_category.return_value = {1: 1200.0}  # 120% → 80 and 100

    counts = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])

    assert counts["events"] == 2
    assert await _count_outbox_events(session_factory) == 2


async def test_run_once_no_crossing_emits_nothing(session_factory, ports) -> None:
    from app.workers.budget_alert_scheduler import run_once

    await _insert_budget(session_factory, month=7, year=2026, amount=1000.0)
    ports[0].get_expenses_by_category.return_value = {1: 100.0}  # 10%

    counts = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])

    assert counts["events"] == 0
    assert await _count_outbox_events(session_factory) == 0


async def test_run_once_upstream_failure_isolated_and_continues(session_factory, ports) -> None:
    from app.domain.exceptions import UpstreamServiceUnavailable
    from app.workers.budget_alert_scheduler import run_once

    await _insert_budget(session_factory, month=7, year=2026, account_id=1, amount=1000.0)
    await _insert_budget(session_factory, month=7, year=2026, account_id=2, amount=1000.0)

    async def flaky_expenses(account_id, start_date, end_date, user_id=0):
        if account_id == 1:
            raise UpstreamServiceUnavailable("transaction-service")
        return {1: 900.0}

    ports[0].get_expenses_by_category.side_effect = flaky_expenses

    counts = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])

    assert counts["budgets"] == 2
    assert counts["failed_upstream"] == 1
    assert counts["events"] == 1  # healthy account still alerted
    assert await _count_outbox_events(session_factory) == 1


async def test_run_once_is_idempotent_at_the_outbox_but_emits_each_tick(session_factory, ports) -> None:
    # The scheduler is stateless: it re-emits every tick. Dedup is downstream
    # (notification-service source_key), NOT here — so two ticks => two outbox rows
    # of the SAME source_key. This documents the accepted churn trade-off.
    from app.workers.budget_alert_scheduler import run_once

    await _insert_budget(session_factory, month=7, year=2026, amount=1000.0)
    ports[0].get_expenses_by_category.return_value = {1: 850.0}

    first = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])
    second = await run_once(session_factory, TODAY, THRESHOLDS, transaction_port=ports[0], category_port=ports[1])

    assert first["events"] == 1
    assert second["events"] == 1
    assert await _count_outbox_events(session_factory) == 2
