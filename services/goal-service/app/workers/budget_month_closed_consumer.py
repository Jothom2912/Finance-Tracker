"""Consumer for budget.month_closed events.

Listens on RabbitMQ, delegates to BudgetMonthClosedHandler which
allocates surplus to the default savings goal (or stores as unallocated).

Connection/topology/retry/DLQ boilerplate lives in the shared
``messaging.ConsumerBase`` (whose queue/DLX/DLQ layout was modelled on
this very consumer). One behavioral fix comes with the base: retries are
republished to this consumer's OWN queue via the default exchange — the
old local copy republished to the topic exchange, re-delivering the
event to every other bound consumer.

Deduplication is handled by the handler itself: _already_handled(source_key)
checks allocation/unallocated tables before writing, and unique constraints
on (source_key, goal_id) / (source_key) catch concurrent races. The
IntegrityError from the race case is caught here and the message ACKed —
it is a benign duplicate, not an error.

ACK timing: the handler commits inside its own UoW context. ConsumerBase
ACKs only after handle() returns (i.e. after DB commit). If the consumer
crashes between commit and ACK, RabbitMQ redelivers; the handler's
source_key check catches the duplicate on the second attempt.

Run as a standalone process::

    python -m app.workers.budget_month_closed_consumer
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_pika.abc import AbstractIncomingMessage
from app.adapters.outbound.unit_of_work import SQLAlchemyBudgetMonthClosedUnitOfWork
from app.application.budget_month_closed_handler import BudgetMonthClosedHandler
from app.config import settings
from app.database import async_session_factory
from contracts.events.budget import BudgetMonthClosedEvent
from messaging import ConsumerBase, PoisonMessageError, setup_worker_logging
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

QUEUE_NAME = "goal_service.budget_month_closed"
ROUTING_KEY = "budget.month_closed"


class BudgetMonthClosedConsumer(ConsumerBase):
    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEY,
        )

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        correlation_id = payload.get("correlation_id", "unknown")

        try:
            event = BudgetMonthClosedEvent.model_validate(payload)
        except Exception as err:
            raise PoisonMessageError(f"Invalid event payload (correlation_id={correlation_id})") from err

        try:
            async with async_session_factory() as session:
                uow = SQLAlchemyBudgetMonthClosedUnitOfWork(session)
                handler = BudgetMonthClosedHandler(uow)
                result = await handler.handle(event)
        except IntegrityError:
            logger.info(
                "Duplicate detected on unique constraint (correlation_id=%s) — benign race, acking",
                correlation_id,
            )
            return

        logger.info(
            "budget.month_closed handled: status=%s source_key=%s amount=%s goal_id=%s",
            result.status,
            result.source_key,
            result.amount,
            result.goal_id,
        )


async def main() -> None:
    setup_worker_logging(__name__)
    await BudgetMonthClosedConsumer().run()


if __name__ == "__main__":
    asyncio.run(main())
