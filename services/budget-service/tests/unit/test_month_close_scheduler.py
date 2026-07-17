"""Tests for the month-close scheduler sweep (F1-07).

``run_once`` drives mod en rigtig (sqlite) DB med injicerede ports — det
dækker både repo-sweep-query'en og worker-logikken. App-imports ligger i
fixtures (house style): settings-singletonen må ikke instantieres ved
collection, før integrationstests har sat deres egne env-vars.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

TODAY = date(2026, 7, 17)


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
    transaction_port.get_expenses_by_category.return_value = {1: 30.0}
    category_port = AsyncMock(spec=ICategoryPort)
    category_port.get_all_names.return_value = {1: "Mad"}
    return transaction_port, category_port


async def _insert_budget(
    session_factory,
    *,
    month: int,
    year: int,
    account_id: int = 1,
    user_id: int = 1,
    amount: float = 100.0,
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


async def _fetch_budget_state(session_factory, budget_id: int):
    from app.models import MonthlyBudgetModel
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(MonthlyBudgetModel.closed_at).where(MonthlyBudgetModel.id == budget_id)
        )
        return result.scalar_one()


async def _count_outbox_events(session_factory) -> int:
    from app.models import OutboxEventModel
    from sqlalchemy import func, select

    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(OutboxEventModel))
        return int(result.scalar_one())


async def test_run_once_closes_due_month_and_writes_outbox(session_factory, ports) -> None:
    from app.workers.month_close_scheduler import run_once

    budget_id = await _insert_budget(session_factory, month=6, year=2026)

    counts = await run_once(session_factory, TODAY, transaction_port=ports[0], category_port=ports[1])

    assert counts["due"] == 1
    assert counts["closed"] == 1
    assert await _fetch_budget_state(session_factory, budget_id) is not None
    assert await _count_outbox_events(session_factory) == 1


async def test_run_once_skips_current_month_and_not_yet_due(session_factory, ports) -> None:
    from app.workers.month_close_scheduler import run_once

    current = await _insert_budget(session_factory, month=7, year=2026)
    # Forrige måned, men "i dag" er d. 6. — før close_day
    previous = await _insert_budget(session_factory, month=6, year=2026, account_id=2)

    counts = await run_once(
        session_factory, date(2026, 7, 6), transaction_port=ports[0], category_port=ports[1]
    )

    assert counts == {
        "due": 0,
        "closed": 0,
        "skipped_already_closed": 0,
        "failed_upstream": 0,
        "failed_unexpected": 0,
    }
    assert await _fetch_budget_state(session_factory, current) is None
    assert await _fetch_budget_state(session_factory, previous) is None


async def test_run_once_skips_manually_closed_month(session_factory, ports) -> None:
    from app.workers.month_close_scheduler import run_once

    await _insert_budget(session_factory, month=6, year=2026, closed_at=datetime(2026, 7, 1, 12, 0))

    counts = await run_once(session_factory, TODAY, transaction_port=ports[0], category_port=ports[1])

    # Allerede lukkede rækker rammer ikke engang sweepen (closed_at IS NULL-filter)
    assert counts["due"] == 0
    assert await _count_outbox_events(session_factory) == 0


async def test_run_once_upstream_failure_leaves_month_open_and_continues(session_factory, ports) -> None:
    from app.domain.exceptions import UpstreamServiceUnavailable
    from app.workers.month_close_scheduler import run_once

    failing = await _insert_budget(session_factory, month=5, year=2026, account_id=1)
    healthy = await _insert_budget(session_factory, month=6, year=2026, account_id=2)

    transaction_port, category_port = ports

    async def flaky_expenses(account_id, start_date, end_date, user_id=0):
        if account_id == 1:
            raise UpstreamServiceUnavailable("transaction-service")
        return {1: 30.0}

    transaction_port.get_expenses_by_category.side_effect = flaky_expenses

    counts = await run_once(session_factory, TODAY, transaction_port=transaction_port, category_port=category_port)

    # Fail-closed: den fejlende måned forbliver åben (retry næste tick),
    # og fejlen isoleres — den anden måned lukkes alligevel.
    assert counts["failed_upstream"] == 1
    assert counts["closed"] == 1
    assert await _fetch_budget_state(session_factory, failing) is None
    assert await _fetch_budget_state(session_factory, healthy) is not None
    assert await _count_outbox_events(session_factory) == 1


async def test_run_once_is_idempotent_across_ticks(session_factory, ports) -> None:
    from app.workers.month_close_scheduler import run_once

    await _insert_budget(session_factory, month=6, year=2026)

    first = await run_once(session_factory, TODAY, transaction_port=ports[0], category_port=ports[1])
    second = await run_once(session_factory, TODAY, transaction_port=ports[0], category_port=ports[1])

    assert first["closed"] == 1
    assert second == {
        "due": 0,
        "closed": 0,
        "skipped_already_closed": 0,
        "failed_upstream": 0,
        "failed_unexpected": 0,
    }
    assert await _count_outbox_events(session_factory) == 1
