"""Consumer for budget.month_closed events.

Listens on RabbitMQ, delegates to BudgetMonthClosedHandler which
allocates surplus to the default savings goal (or stores as unallocated).

Deduplication is handled by the handler itself: _already_handled(source_key)
checks allocation/unallocated tables before writing, and unique constraints
on (source_key, goal_id) / (source_key) catch concurrent races.  The
consumer catches IntegrityError from the race case and ACKs — it is a
benign duplicate, not an error.

ACK timing: the handler commits inside its own UoW context.  The consumer
ACKs only after handle() returns (i.e. after DB commit).  If the consumer
crashes between commit and ACK, RabbitMQ redelivers; the handler's
source_key check catches the duplicate on the second attempt.

Run as a standalone process::

    python -m app.workers.budget_month_closed_consumer
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage
from contracts.events.budget import BudgetMonthClosedEvent
from sqlalchemy.exc import IntegrityError

from app.adapters.outbound.unit_of_work import SQLAlchemyBudgetMonthClosedUnitOfWork
from app.application.budget_month_closed_handler import BudgetMonthClosedHandler
from app.config import settings
from app.database import async_session_factory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "goal_service.budget_month_closed"
ROUTING_KEY = "budget.month_closed"
MAX_RETRIES = 3


class BudgetMonthClosedConsumer:

    def __init__(self) -> None:
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None

    async def run(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

        exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )

        dlx = await self._channel.declare_exchange(
            f"{EXCHANGE_NAME}.dlx",
            ExchangeType.DIRECT,
            durable=True,
        )
        dlq = await self._channel.declare_queue(f"{QUEUE_NAME}.dlq", durable=True)
        await dlq.bind(dlx, routing_key=QUEUE_NAME)

        queue = await self._channel.declare_queue(
            QUEUE_NAME,
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{EXCHANGE_NAME}.dlx",
                "x-dead-letter-routing-key": QUEUE_NAME,
            },
        )
        await queue.bind(exchange, routing_key=ROUTING_KEY)

        await queue.consume(self._on_message)
        logger.info("Consumer %s listening on %s", QUEUE_NAME, ROUTING_KEY)
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        correlation_id = body.get("correlation_id", "unknown")

        try:
            event = BudgetMonthClosedEvent.model_validate(body)
        except Exception:
            logger.error(
                "Invalid event payload (correlation_id=%s) — sending to DLQ",
                correlation_id,
                exc_info=True,
            )
            await message.nack(requeue=False)
            return

        try:
            async with async_session_factory() as session:
                uow = SQLAlchemyBudgetMonthClosedUnitOfWork(session)
                handler = BudgetMonthClosedHandler(uow)
                result = await handler.handle(event)

            logger.info(
                "budget.month_closed handled: status=%s source_key=%s amount=%s goal_id=%s",
                result.status,
                result.source_key,
                result.amount,
                result.goal_id,
            )
            await message.ack()

        except IntegrityError:
            logger.info(
                "Duplicate detected on unique constraint (correlation_id=%s) — benign race, acking",
                correlation_id,
            )
            await message.ack()

        except Exception:
            retry_count = int((message.headers or {}).get("x-retry-count", 0))
            if retry_count < MAX_RETRIES:
                logger.warning(
                    "Handler failed (retry=%d/%d, correlation_id=%s) — republishing",
                    retry_count + 1,
                    MAX_RETRIES,
                    correlation_id,
                    exc_info=True,
                )
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error(
                    "Max retries reached (correlation_id=%s) — sending to DLQ",
                    correlation_id,
                    exc_info=True,
                )
                await message.nack(requeue=False)

    async def _republish(self, original: AbstractIncomingMessage, retry_count: int) -> None:
        assert self._channel is not None
        exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )
        headers = dict(original.headers or {})
        headers["x-retry-count"] = retry_count
        msg = aio_pika.Message(
            body=original.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        await exchange.publish(msg, routing_key=ROUTING_KEY)


async def main() -> None:
    consumer = BudgetMonthClosedConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
