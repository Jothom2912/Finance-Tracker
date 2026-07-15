"""Consumer for saga start events (saga.*.start).

Initiates new sagas when start events arrive.

Connection/topology/retry/DLQ boilerplate lives in the shared
``messaging.ConsumerBase``.  Domain-exception mapping preserved:
``DuplicateSaga`` is benign (ack), malformed start events and
``SagaDomainError`` are unrecoverable (DLQ via ``PoisonMessageError``),
anything else takes the base's retry ladder.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_pika.abc import AbstractIncomingMessage
from messaging import ConsumerBase, PoisonMessageError, setup_worker_logging

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.orchestrator import SagaOrchestrator, SagaRegistry
from app.application.sagas import get_saga_registry
from app.config import settings
from app.database import async_session_factory
from app.domain.exceptions import DuplicateSaga, SagaDomainError

logger = logging.getLogger(__name__)

QUEUE_NAME = "saga_service.saga_start"
ROUTING_KEY = "saga.*.start"
MAX_RETRIES = 3


class SagaStartConsumer(ConsumerBase):
    def __init__(self, registry: SagaRegistry) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEY,
            max_retries=MAX_RETRIES,
        )
        self._registry = registry

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        try:
            saga_type, context, correlation_id = self._parse_start_event(payload)
        except (KeyError, ValueError) as exc:
            raise PoisonMessageError(f"Invalid saga start event: {exc}") from exc

        try:
            async with async_session_factory() as session:
                uow = SQLAlchemyUnitOfWork(session)
                orchestrator = SagaOrchestrator(uow, self._registry)
                saga = await orchestrator.start_saga(saga_type, context, correlation_id)
        except DuplicateSaga:
            logger.info("Duplicate saga start for correlation=%s — acking", correlation_id)
            return
        except SagaDomainError as exc:
            raise PoisonMessageError(f"Domain error starting saga type={saga_type}: {exc}") from exc

        logger.info("Started saga type=%s id=%s", saga_type, saga.id)

    @staticmethod
    def _parse_start_event(body: dict) -> tuple[str, dict, str | None]:
        correlation_id = body.get("correlation_id")
        event_type = body.get("event_type", "")

        if event_type == "saga.bank_sync.start" or body.get("saga_type") == "bank_sync":
            context = {
                "connection_id": body["connection_id"],
                "user_id": body["user_id"],
                "account_id": body["account_id"],
                "account_name": body["account_name"],
                "bank_account_uid": body["bank_account_uid"],
            }
            if body.get("date_from"):
                context["date_from"] = body["date_from"]
            return "bank_sync", context, correlation_id

        saga_type = body.get("saga_type")
        if not saga_type:
            raise ValueError("missing saga_type")
        return saga_type, body.get("context", {}), correlation_id


async def main() -> None:
    setup_worker_logging(__name__)
    registry = get_saga_registry()
    consumer = SagaStartConsumer(registry)
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
