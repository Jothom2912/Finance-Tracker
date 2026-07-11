"""Background worker that handles stale sagas.

Stale executing sagas are compensated (if there is anything to undo) or marked
timed_out; stale compensations get their command re-emitted once, then fail.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.orchestrator import SagaOrchestrator, SagaRegistry
from app.application.sagas import get_saga_registry
from app.config import settings
from app.database import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


class SagaTimeoutWorker:
    def __init__(
        self,
        registry: SagaRegistry,
        *,
        interval_seconds: float,
        timeout_seconds: int,
    ) -> None:
        self._registry = registry
        self._interval = interval_seconds
        self._max_age = timedelta(seconds=timeout_seconds)

    async def run_forever(self) -> None:
        logger.info(
            "Saga timeout worker started (interval=%ss, timeout=%ss)",
            self._interval,
            self._max_age.total_seconds(),
        )
        while True:
            await self._check_once()
            await asyncio.sleep(self._interval)

    async def _check_once(self) -> None:
        async with async_session_factory() as session:
            uow = SQLAlchemyUnitOfWork(session)
            orchestrator = SagaOrchestrator(uow, self._registry)
            handled = await orchestrator.check_timeouts(self._max_age)
            if handled:
                logger.info("Handled %d stale saga(s) (timed out / compensating)", len(handled))


async def main() -> None:
    registry = get_saga_registry()
    worker = SagaTimeoutWorker(
        registry,
        interval_seconds=float(settings.TIMEOUT_CHECK_INTERVAL_SECONDS),
        timeout_seconds=settings.SAGA_TIMEOUT_SECONDS,
    )
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
