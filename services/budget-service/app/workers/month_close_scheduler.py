"""Scheduled month-close worker (F1-07) — ADR-0003's day-7 trigger.

Every tick: find open budgets for past periods, close the ones that are due
(day >= MONTH_CLOSE_DAY in the month after the budget month) through the same
``MonthlyBudgetService.close_month`` use case as the manual button — same
fail-closed guard (P1-01), same 409-semantics, same event.

Idempotency lives in the data layer, not here: ``mark_closed`` is a
conditional UPDATE (one winner vs the manual button) and the goal-side
consumer dedups on ``source_key`` — a crash-restart mid-sweep is harmless.

Each tick recomputes what is due from the DB, so missed ticks self-heal.
Run as a standalone process (single replica)::

    python -m app.workers.month_close_scheduler

See dev-notes/decisions/2026-07-17-scheduler-pattern-worker-loop.md.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

from messaging import setup_worker_logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.category_port import CategoryPort
from app.adapters.outbound.postgres_monthly_budget_repository import (
    PostgresMonthlyBudgetRepository,
)
from app.adapters.outbound.transaction_port import TransactionPort
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.monthly_budget_service import MonthlyBudgetService
from app.application.ports.outbound import ICategoryPort, ITransactionPort
from app.config import settings
from app.domain.exceptions import (
    MonthlyBudgetAlreadyClosed,
    MonthlyBudgetNotFound,
    UpstreamServiceUnavailable,
)
from app.domain.scheduled_close import is_due_for_scheduled_close

logger = logging.getLogger(__name__)


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    today: date,
    close_day: int = 7,
    transaction_port: ITransactionPort | None = None,
    category_port: ICategoryPort | None = None,
) -> dict[str, int]:
    """One sweep. Returns counters for the tick-summary log (and tests).

    Ports are injectable for tests; the real HTTP adapters are stateless, so
    one instance per sweep is fine.
    """
    transaction_port = transaction_port or TransactionPort()
    category_port = category_port or CategoryPort()
    counts = {"due": 0, "closed": 0, "skipped_already_closed": 0, "failed_upstream": 0, "failed_unexpected": 0}

    async with session_factory() as session:
        candidates = await PostgresMonthlyBudgetRepository(session).list_open_before_period(today.year, today.month)

    due = [b for b in candidates if is_due_for_scheduled_close(b.year, b.month, today, close_day)]
    counts["due"] = len(due)

    for budget in due:
        # Egen session per budget: én fejlende måned må ikke vælte de andre,
        # og close_month committer selv (closed_at + outbox atomisk).
        async with session_factory() as session:
            service = MonthlyBudgetService(
                uow=SQLAlchemyUnitOfWork(session),
                transaction_port=transaction_port,
                category_port=category_port,
            )
            try:
                await service.close_month(
                    budget.account_id,
                    budget.year,
                    budget.month,
                    user_id=budget.user_id,
                )
                counts["closed"] += 1
                logger.info(
                    "scheduled close: %02d/%d closed for account %s",
                    budget.month,
                    budget.year,
                    budget.account_id,
                )
            except (MonthlyBudgetAlreadyClosed, MonthlyBudgetNotFound):
                # Tabt kapløb med "Luk måned"-knappen (eller rækken slettet
                # mellem sweep og close) — præcis hvad idempotensen er til.
                counts["skipped_already_closed"] += 1
                logger.info(
                    "scheduled close: %02d/%d for account %s already closed/gone — skipping",
                    budget.month,
                    budget.year,
                    budget.account_id,
                )
            except UpstreamServiceUnavailable:
                # Fail-closed (P1-01): måneden er IKKE lukket; næste tick prøver igen.
                counts["failed_upstream"] += 1
                logger.warning(
                    "scheduled close: %02d/%d for account %s NOT closed — transaction-service unavailable, retrying next tick",
                    budget.month,
                    budget.year,
                    budget.account_id,
                )
            except Exception:
                counts["failed_unexpected"] += 1
                logger.exception(
                    "scheduled close: unexpected error closing %02d/%d for account %s",
                    budget.month,
                    budget.year,
                    budget.account_id,
                )

    logger.info(
        "scheduled close tick: %d candidate(s), %d due, %d closed, %d skipped, %d upstream-failed, %d unexpected",
        len(candidates),
        counts["due"],
        counts["closed"],
        counts["skipped_already_closed"],
        counts["failed_upstream"],
        counts["failed_unexpected"],
    )
    return counts


async def main() -> None:
    setup_worker_logging(__name__)
    from app.database import async_session_factory

    logger.info(
        "month-close scheduler starting: interval=%ss, close_day=%s",
        settings.MONTH_CLOSE_INTERVAL_SECONDS,
        settings.MONTH_CLOSE_DAY,
    )
    while True:
        today = datetime.now(timezone.utc).date()
        try:
            await run_once(async_session_factory, today, settings.MONTH_CLOSE_DAY)
        except Exception:
            # En fejlende sweep (fx DB nede) må ikke dræbe loopet — next tick.
            logger.exception("month-close scheduler tick failed")
        await asyncio.sleep(settings.MONTH_CLOSE_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
