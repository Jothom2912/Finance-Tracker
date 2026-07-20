"""Mid-month budget-alert scheduler (F2-03).

Every tick: find open budgets for the *running* period and, per budget, emit a
``BudgetLineThresholdCrossedEvent`` for every line at/over a configured threshold
(default 80% and 100%) through ``MonthlyBudgetService.evaluate_alerts`` — same
fail-closed spent computation as ``close_month`` (P1-01).

Stateless by design: the scheduler keeps no memory of what it already emitted, so
it re-emits every crossing each tick. "Notify once per line/threshold/period" is
enforced downstream by notification-service's unique ``source_key`` (IntegrityError
→ ACK). Trade-off: a little redundant outbox/consumer churn per tick, accepted to
avoid a fired-alerts state table that would duplicate computable idempotency info.
See dev-notes/plans/2026-07-20-f203-mid-month-budget-alerts.md.

Each tick recomputes from the DB, so missed ticks self-heal. Run as a standalone
process (single replica)::

    python -m app.workers.budget_alert_scheduler

Reuses the worker-loop pattern of the month-close scheduler
(dev-notes/decisions/2026-07-17-scheduler-pattern-worker-loop.md).
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
from app.domain.exceptions import UpstreamServiceUnavailable

logger = logging.getLogger(__name__)


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    today: date,
    thresholds: list[int],
    transaction_port: ITransactionPort | None = None,
    category_port: ICategoryPort | None = None,
) -> dict[str, int]:
    """One sweep of the running period. Returns counters for the tick log (and tests).

    Ports are injectable for tests; the real HTTP adapters are stateless, so one
    instance per sweep is fine.
    """
    transaction_port = transaction_port or TransactionPort()
    category_port = category_port or CategoryPort()
    counts = {"budgets": 0, "events": 0, "failed_upstream": 0, "failed_unexpected": 0}

    async with session_factory() as session:
        candidates = await PostgresMonthlyBudgetRepository(session).list_open_for_period(
            today.year,
            today.month,
        )
    counts["budgets"] = len(candidates)

    for budget in candidates:
        # Egen session per budget: én fejlende evaluering må ikke vælte de andre,
        # og evaluate_alerts committer selv sine outbox-rækker.
        async with session_factory() as session:
            service = MonthlyBudgetService(
                uow=SQLAlchemyUnitOfWork(session),
                transaction_port=transaction_port,
                category_port=category_port,
            )
            try:
                events = await service.evaluate_alerts(budget, today, thresholds)
                counts["events"] += len(events)
            except UpstreamServiceUnavailable:
                # Fail-closed: hellere ingen advarsel end en falsk "0% brugt".
                # Næste tick prøver igen.
                counts["failed_upstream"] += 1
                logger.warning(
                    "budget alerts: %02d/%d account %s skipped — transaction-service unavailable, retrying next tick",
                    budget.month,
                    budget.year,
                    budget.account_id,
                )
            except Exception:
                counts["failed_unexpected"] += 1
                logger.exception(
                    "budget alerts: unexpected error evaluating %02d/%d for account %s",
                    budget.month,
                    budget.year,
                    budget.account_id,
                )

    logger.info(
        "budget-alert tick: %d open budget(s), %d event(s) emitted, %d upstream-failed, %d unexpected",
        counts["budgets"],
        counts["events"],
        counts["failed_upstream"],
        counts["failed_unexpected"],
    )
    return counts


async def main() -> None:
    setup_worker_logging(__name__)
    from app.database import async_session_factory

    thresholds = settings.budget_alert_thresholds
    logger.info(
        "budget-alert scheduler starting: interval=%ss, thresholds=%s",
        settings.BUDGET_ALERT_INTERVAL_SECONDS,
        thresholds,
    )
    while True:
        today = datetime.now(timezone.utc).date()
        try:
            await run_once(async_session_factory, today, thresholds)
        except Exception:
            # En fejlende sweep (fx DB nede) må ikke dræbe loopet — next tick.
            logger.exception("budget-alert scheduler tick failed")
        await asyncio.sleep(settings.BUDGET_ALERT_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
