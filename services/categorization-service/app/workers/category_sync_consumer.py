"""Consumer for category.* events from transaction-service.

Keeps cat-service's local categories table in sync with
transaction-service (current source of truth for categories).

Handles: category.created, category.updated, category.deleted.

This consumer exists because categories-CRUD ownership has not yet
been transferred to cat-service (see ADR-002). Once transferred,
this consumer becomes unnecessary and should be removed.

Run as a standalone process::

    python -m app.workers.category_sync_consumer
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models import CategoryModel, ProcessedEventModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "categorization.category_sync"
ROUTING_KEY = "category.*"
MAX_RETRIES = 3


class CategorySyncConsumer:
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
        message_id = body.get("correlation_id", "")
        event_type = body.get("event_type", "")

        try:
            async with async_session_factory() as session:
                if message_id and await self._is_duplicate(session, message_id):
                    await message.ack()
                    return

                if event_type == "category.created":
                    await self._sync_created(session, body)
                elif event_type == "category.updated":
                    await self._sync_updated(session, body)
                elif event_type == "category.deleted":
                    await self._sync_deleted(session, body)
                else:
                    logger.warning("Unknown event_type: %s", event_type)
                    await message.ack()
                    return

                if message_id:
                    self._add_inbox_row(session, message_id, event_type)

                try:
                    await session.commit()
                except IntegrityError as exc:
                    await session.rollback()
                    if "processed_events" in str(exc).lower() or "uq_processed_events" in str(exc).lower():
                        logger.info("Duplicate on commit (message_id=%s)", message_id)
                        await message.ack()
                        return
                    raise

            await message.ack()

        except Exception:
            retry_count = int((message.headers or {}).get("x-retry-count", 0))
            if retry_count < MAX_RETRIES:
                logger.warning("Handler failed (retry=%d/%d)", retry_count + 1, MAX_RETRIES, exc_info=True)
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error("Max retries reached — DLQ", exc_info=True)
                await message.nack(requeue=False)

    async def _sync_created(self, session: AsyncSession, body: dict) -> None:
        cat_id = body.get("category_id")
        name = body.get("name", "")
        cat_type = body.get("category_type", "expense")

        existing = await session.get(CategoryModel, cat_id)
        if existing is not None:
            return

        session.add(CategoryModel(id=cat_id, name=name, type=cat_type))
        logger.info("Synced category.created: id=%s name='%s'", cat_id, name)

    async def _sync_updated(self, session: AsyncSession, body: dict) -> None:
        cat_id = body.get("category_id")
        existing = await session.get(CategoryModel, cat_id)

        if existing is None:
            session.add(
                CategoryModel(
                    id=cat_id,
                    name=body.get("name", ""),
                    type=body.get("category_type", "expense"),
                )
            )
            logger.info("Synced category.updated as create (missing): id=%s", cat_id)
            return

        existing.name = body.get("name", existing.name)
        existing.type = body.get("category_type", existing.type)
        logger.info("Synced category.updated: id=%s name='%s'", cat_id, existing.name)

    async def _sync_deleted(self, session: AsyncSession, body: dict) -> None:
        cat_id = body.get("category_id")
        existing = await session.get(CategoryModel, cat_id)
        if existing is not None:
            await session.delete(existing)
            logger.info("Synced category.deleted: id=%s", cat_id)

    @staticmethod
    async def _is_duplicate(session: AsyncSession, message_id: str) -> bool:
        stmt = select(ProcessedEventModel).where(
            ProcessedEventModel.message_id == message_id,
            ProcessedEventModel.consumer_name == QUEUE_NAME,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _add_inbox_row(session: AsyncSession, message_id: str, event_type: str) -> None:
        session.add(
            ProcessedEventModel(
                message_id=message_id,
                consumer_name=QUEUE_NAME,
                event_type=event_type,
            )
        )

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
        await exchange.publish(msg, routing_key=original.routing_key or ROUTING_KEY)


async def main() -> None:
    consumer = CategorySyncConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
