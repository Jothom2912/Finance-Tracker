"""Consumer for saga reply events (saga.reply.*).

Receives replies from participant services and advances/compensates sagas.

Connection/topology/retry/DLQ boilerplate lives in the shared
``messaging.ConsumerBase``.  Domain-exception mapping preserved:
``SagaAlreadyCompleted`` is a benign duplicate (ack), ``SagaDomainError``
is unrecoverable (straight to DLQ via ``PoisonMessageError``), anything
else takes the base's retry ladder.
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
from app.domain.exceptions import SagaAlreadyCompleted, SagaDomainError

logger = logging.getLogger(__name__)

QUEUE_NAME = "saga_service.saga_reply"
ROUTING_KEY = "saga.reply.#"
MAX_RETRIES = 3


class SagaReplyConsumer(ConsumerBase):
    def __init__(self, registry: SagaRegistry) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEY,
            max_retries=MAX_RETRIES,
        )
        self._registry = registry

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        saga_id = payload.get("saga_id")
        step_name = payload.get("step_name")
        success = payload.get("success", False)
        result_data = payload.get("result_data")
        error_message = payload.get("error_message")
        is_compensation = payload.get("is_compensation", False)

        if not saga_id or not step_name:
            raise PoisonMessageError("Invalid saga reply: missing saga_id or step_name")

        try:
            async with async_session_factory() as session:
                uow = SQLAlchemyUnitOfWork(session)
                orchestrator = SagaOrchestrator(uow, self._registry)
                if is_compensation:
                    await orchestrator.handle_compensation_reply(saga_id, step_name, success, error_message)
                else:
                    await orchestrator.handle_reply(saga_id, step_name, success, result_data, error_message)
        except SagaAlreadyCompleted:
            logger.info("Duplicate reply for completed saga=%s step=%s — acking", saga_id, step_name)
            return
        except SagaDomainError as exc:
            raise PoisonMessageError(f"Domain error processing reply saga={saga_id}: {exc}") from exc

        logger.info("Processed reply for saga=%s step=%s success=%s", saga_id, step_name, success)


async def main() -> None:
    setup_worker_logging(__name__)
    registry = get_saga_registry()
    consumer = SagaReplyConsumer(registry)
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
