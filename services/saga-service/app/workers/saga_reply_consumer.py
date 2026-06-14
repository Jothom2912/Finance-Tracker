"""Consumer for saga reply events (saga.reply.*).

Receives replies from participant services and advances/compensates sagas.
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.orchestrator import SagaOrchestrator, SagaRegistry
from app.application.sagas import get_saga_registry
from app.config import settings
from app.database import async_session_factory
from app.domain.exceptions import SagaAlreadyCompleted, SagaDomainError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "saga_service.saga_reply"
ROUTING_KEY = "saga.reply.#"
MAX_RETRIES = 3


class SagaReplyConsumer:
    def __init__(self, registry: SagaRegistry) -> None:
        self._registry = registry
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)

        dlx = await self._channel.declare_exchange(f"{EXCHANGE_NAME}.dlx", ExchangeType.DIRECT, durable=True)
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

        logger.info("Saga reply consumer started, listening on %s", ROUTING_KEY)
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        saga_id = body.get("saga_id")
        step_name = body.get("step_name")
        success = body.get("success", False)
        result_data = body.get("result_data")
        error_message = body.get("error_message")
        is_compensation = body.get("is_compensation", False)

        if not saga_id or not step_name:
            logger.error("Invalid saga reply: missing saga_id or step_name — sending to DLQ")
            await message.nack(requeue=False)
            return

        try:
            async with async_session_factory() as session:
                uow = SQLAlchemyUnitOfWork(session)
                orchestrator = SagaOrchestrator(uow, self._registry)
                if is_compensation:
                    await orchestrator.handle_compensation_reply(saga_id, step_name)
                else:
                    await orchestrator.handle_reply(saga_id, step_name, success, result_data, error_message)

            await message.ack()
            logger.info("Processed reply for saga=%s step=%s success=%s", saga_id, step_name, success)

        except SagaAlreadyCompleted:
            logger.info("Duplicate reply for completed saga=%s step=%s — acking", saga_id, step_name)
            await message.ack()
        except SagaDomainError as exc:
            logger.warning("Domain error processing reply saga=%s: %s", saga_id, exc)
            await message.nack(requeue=False)
        except Exception:
            retry_count = (message.headers or {}).get("x-retry-count", 0)
            if isinstance(retry_count, bytes):
                retry_count = int(retry_count)
            if retry_count >= MAX_RETRIES:
                logger.error("Max retries for saga reply saga=%s step=%s — DLQ", saga_id, step_name, exc_info=True)
                await message.nack(requeue=False)
            else:
                logger.warning("Retrying saga reply saga=%s (attempt %d)", saga_id, retry_count + 1, exc_info=True)
                await self._republish(message, retry_count + 1)
                await message.ack()

    async def _republish(self, original: AbstractIncomingMessage, retry_count: int) -> None:
        if self._channel is None:
            return
        exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
        headers = dict(original.headers or {})
        headers["x-retry-count"] = retry_count
        msg = aio_pika.Message(
            body=original.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        routing_key = original.routing_key or "saga.reply.unknown"
        await exchange.publish(msg, routing_key=routing_key)


async def main() -> None:
    registry = get_saga_registry()
    consumer = SagaReplyConsumer(registry)
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
