"""Consumer for saga start events (saga.*.start).

Initiates new sagas when start events arrive.
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
from app.domain.exceptions import DuplicateSaga, SagaDomainError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "saga_service.saga_start"
ROUTING_KEY = "saga.*.start"
MAX_RETRIES = 3


class SagaStartConsumer:
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

        logger.info("Saga start consumer started, listening on %s", ROUTING_KEY)
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        try:
            saga_type, context, correlation_id = self._parse_start_event(body)
        except (KeyError, ValueError) as exc:
            logger.error("Invalid saga start event: %s — sending to DLQ", exc)
            await message.nack(requeue=False)
            return

        try:
            async with async_session_factory() as session:
                uow = SQLAlchemyUnitOfWork(session)
                orchestrator = SagaOrchestrator(uow, self._registry)
                saga = await orchestrator.start_saga(saga_type, context, correlation_id)

            await message.ack()
            logger.info("Started saga type=%s id=%s", saga_type, saga.id)

        except DuplicateSaga:
            logger.info("Duplicate saga start for correlation=%s — acking", correlation_id)
            await message.ack()
        except SagaDomainError as exc:
            logger.warning("Domain error starting saga type=%s: %s", saga_type, exc)
            await message.nack(requeue=False)
        except Exception:
            retry_count = (message.headers or {}).get("x-retry-count", 0)
            if isinstance(retry_count, bytes):
                retry_count = int(retry_count)
            if retry_count >= MAX_RETRIES:
                logger.error("Max retries for saga start type=%s — DLQ", saga_type, exc_info=True)
                await message.nack(requeue=False)
            else:
                logger.warning("Retrying saga start type=%s (attempt %d)", saga_type, retry_count + 1, exc_info=True)
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
        routing_key = original.routing_key or "saga.unknown.start"
        await exchange.publish(msg, routing_key=routing_key)

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
    registry = get_saga_registry()
    consumer = SagaStartConsumer(registry)
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
