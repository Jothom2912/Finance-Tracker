"""Scheduled bank-sync worker (F1-05) — nightly sync per active connection.

Every tick: find active connections whose last sync is older than
``SYNC_EVERY_HOURS`` and start a sync saga for each through the SAME
``BankingService.start_sync_saga`` use case as the manual button — same
in-flight claim (P3-14), same consent gate, same event. ``bearer_token``
is None, so on a claim conflict the scheduler simply defers to the running
saga (``already_running``); stale claims recover via the TTL inside
``try_claim_sync``.

Staleness-based rather than fixed clock-hour: each tick recomputes what is
due from the DB, so missed ticks self-heal (scheduler-pattern rule 3).
Consent handling is the v1 reconsent surface: expired → skipped with a
WARNING; expiring within ``SYNC_CONSENT_WARN_DAYS`` → synced but warned.

Run as a standalone process (single replica)::

    python -m app.workers.sync_scheduler

See dev-notes/decisions/2026-07-17-scheduler-pattern-worker-loop.md.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.postgres_bank_connection_repository import (
    PostgresBankConnectionRepository,
)
from app.application.service import BankingService
from app.config import settings
from app.domain.exceptions import BankConsentExpired

logger = logging.getLogger(__name__)

ServiceFactory = Callable[[AsyncSession], BankingService]


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    now: datetime,
    service_factory: ServiceFactory,
    *,
    every_hours: int = 24,
    consent_warn_days: int = 7,
) -> dict[str, int]:
    """One sweep. Returns counters for the tick-summary log (and tests)."""
    counts = {"due": 0, "started": 0, "already_running": 0, "consent_expired": 0, "failed": 0}

    cutoff = now - timedelta(hours=every_hours)
    async with session_factory() as session:
        candidates = await PostgresBankConnectionRepository(session).list_active_synced_before(cutoff)

    due = [c for c in candidates if c.is_sync_due(now, every_hours)]
    counts["due"] = len(due)

    for conn in due:
        if conn.is_expired_at(now):
            # v1-reconsent-fladen: ingen dødsdømt saga — brugeren skal
            # forny samtykket via connect-flowet.
            counts["consent_expired"] += 1
            logger.warning(
                "scheduled sync: connection %s (account %s) skipped — consent expired %s, reconsent required",
                conn.id,
                conn.account_id,
                conn.expires_at,
            )
            continue
        if conn.expires_at is not None and conn.is_expired_at(now + timedelta(days=consent_warn_days)):
            logger.warning(
                "scheduled sync: connection %s consent expires %s (within %d days) — reconsent soon",
                conn.id,
                conn.expires_at,
                consent_warn_days,
            )

        # Egen session per forbindelse: én fejlende sync må ikke vælte de
        # andre, og claim+event committes af use casen selv.
        async with session_factory() as session:
            service = service_factory(session)
            try:
                saga_id, already_running = await service.start_sync_saga(
                    conn.id,  # type: ignore[arg-type]  # rows fra DB har altid id
                    user_id=conn.user_id,
                    bearer_token=None,
                )
                if already_running:
                    counts["already_running"] += 1
                    logger.info(
                        "scheduled sync: connection %s already syncing (saga %s) — deferring",
                        conn.id,
                        saga_id,
                    )
                else:
                    counts["started"] += 1
                    logger.info(
                        "scheduled sync: started saga %s for connection %s (account %s)",
                        saga_id,
                        conn.id,
                        conn.account_id,
                    )
            except BankConsentExpired:
                # Backstop — burde være fanget af entity-tjekket ovenfor.
                counts["consent_expired"] += 1
                logger.warning("scheduled sync: connection %s consent expired (use-case gate)", conn.id)
            except Exception:
                counts["failed"] += 1
                logger.exception("scheduled sync: unexpected error for connection %s", conn.id)

    logger.info(
        "scheduled sync tick: %d candidate(s), %d due, %d started, %d already-running, %d consent-expired, %d failed",
        len(candidates),
        counts["due"],
        counts["started"],
        counts["already_running"],
        counts["consent_expired"],
        counts["failed"],
    )
    return counts


def _build_service_factory() -> ServiceFactory:
    # Samme wiring som API'ens DI (dependencies.py). EB-klienten bygges én
    # gang (PEM-smoke-test ved konstruktion, delt TCP-pool) selvom
    # start_sync_saga aldrig kalder EB — det holder wiring identisk med API'en.
    from app.adapters.outbound.account_adapter import AccountServiceAdapter
    from app.adapters.outbound.enable_banking_client import (
        EnableBankingClient,
        EnableBankingConfig,
    )
    from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork

    banking_client = EnableBankingClient(
        EnableBankingConfig(
            app_id=settings.ENABLE_BANKING_APP_ID,
            key_path=settings.ENABLE_BANKING_KEY_PATH,
            redirect_uri=settings.ENABLE_BANKING_REDIRECT_URI,
            max_tx_pages=settings.MAX_TX_PAGES,
        )
    )
    account_port = AccountServiceAdapter(
        base_url=settings.ACCOUNT_SERVICE_URL,
        api_key=settings.INTERNAL_API_KEY,
        timeout=settings.ACCOUNT_SERVICE_TIMEOUT,
    )

    def factory(session: AsyncSession) -> BankingService:
        return BankingService(
            uow=SQLAlchemyUnitOfWork(session),
            account_port=account_port,
            banking_client=banking_client,
            saga_status_port=None,  # bearer_token er None — konflikt = defer
        )

    return factory


async def main() -> None:
    from messaging import setup_worker_logging

    from app.database import async_session_factory

    setup_worker_logging(__name__)
    service_factory = _build_service_factory()
    logger.info(
        "bank-sync scheduler starting: interval=%ss, every=%sh, consent-warn=%sd",
        settings.SYNC_SCHEDULER_INTERVAL_SECONDS,
        settings.SYNC_EVERY_HOURS,
        settings.SYNC_CONSENT_WARN_DAYS,
    )
    while True:
        now = datetime.now(timezone.utc)
        try:
            await run_once(
                async_session_factory,
                now,
                service_factory,
                every_hours=settings.SYNC_EVERY_HOURS,
                consent_warn_days=settings.SYNC_CONSENT_WARN_DAYS,
            )
        except Exception:
            # En fejlende sweep (fx DB nede) må ikke dræbe loopet — next tick.
            logger.exception("bank-sync scheduler tick failed")
        await asyncio.sleep(settings.SYNC_SCHEDULER_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
