"""Consumer for category.* and subcategory.* events from categorization-service.

Per ADR-003 categorization-service owns the taxonomy; this consumer keeps
transaction-service's local read copies (``categories``, ``subcategories``)
synchronized so write paths can resolve denormalized names and validate
subcategory-belongs-to-category without HTTP calls.

Self-healing: events carry full state, so an ``*.updated`` for a row we
never saw simply creates it (upsert), and ``*.deleted`` for a missing row
is a no-op. Note that ``display_order`` is deliberately NOT projected —
ordering is a presentation concern served by categorization-service.

Atomicity: upsert/delete + inbox row committed in one DB transaction.
Idempotency: inbox pattern on (message_id, consumer_name) with UNIQUE constraint.

Run as a standalone process::

    python -m app.workers.taxonomy_sync_consumer
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
from app.models import CategoryModel, ProcessedEventModel, SubCategoryModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "transaction_service.taxonomy_sync"
ROUTING_KEYS = ("category.*", "subcategory.*")
MAX_RETRIES = 5


class TaxonomySyncConsumer:
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
        for routing_key in ROUTING_KEYS:
            await queue.bind(exchange, routing_key=routing_key)

        await queue.consume(self._on_message)
        logger.info("Consumer %s listening on %s", QUEUE_NAME, ", ".join(ROUTING_KEYS))
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        message_id = body.get("correlation_id", "")
        event_type = body.get("event_type", "")

        try:
            async with async_session_factory() as session:
                if message_id and await self._is_duplicate(session, message_id):
                    logger.info("Skipping duplicate (message_id=%s)", message_id)
                    await message.ack()
                    return

                handled = await self._dispatch(session, event_type, body)
                if not handled:
                    logger.warning("Unknown event_type %r — acking without action", event_type)
                    await message.ack()
                    return

                if message_id:
                    self._add_inbox_row(session, message_id, event_type)

                try:
                    await session.commit()
                except IntegrityError as exc:
                    await session.rollback()
                    if "processed_events" in str(exc).lower() or "uq_processed_events" in str(exc).lower():
                        logger.info("Duplicate on commit (message_id=%s) — benign race", message_id)
                        await message.ack()
                        return
                    raise

            await message.ack()

        except Exception:
            retry_count = int((message.headers or {}).get("x-retry-count", 0))
            if retry_count < MAX_RETRIES:
                logger.warning(
                    "Handler failed for %s (retry=%d/%d)",
                    event_type,
                    retry_count + 1,
                    MAX_RETRIES,
                    exc_info=True,
                )
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error("Max retries reached for %s — DLQ", event_type, exc_info=True)
                await message.nack(requeue=False)

    async def _dispatch(self, session: AsyncSession, event_type: str, body: dict) -> bool:
        if event_type in ("category.created", "category.updated"):
            await self._upsert_category(session, body)
        elif event_type == "category.deleted":
            await self._delete_category(session, body)
        elif event_type in ("subcategory.created", "subcategory.updated"):
            await self._upsert_subcategory(session, body)
        elif event_type == "subcategory.deleted":
            await self._delete_subcategory(session, body)
        else:
            return False
        return True

    @staticmethod
    async def _upsert_category(session: AsyncSession, body: dict) -> None:
        category_id = body["category_id"]
        model = await session.get(CategoryModel, category_id)
        if model is None:
            # Self-healing: an update for a row we never saw creates it.
            session.add(
                CategoryModel(
                    id=category_id,
                    name=body["name"],
                    type=body["category_type"],
                )
            )
            logger.info("Category %s created in read copy", category_id)
        else:
            model.name = body["name"]
            model.type = body["category_type"]
            logger.info("Category %s updated in read copy", category_id)

    @staticmethod
    async def _delete_category(session: AsyncSession, body: dict) -> None:
        model = await session.get(CategoryModel, body["category_id"])
        if model is None:
            logger.info("Category %s already absent — no-op", body["category_id"])
            return
        await session.delete(model)
        logger.info("Category %s removed from read copy", body["category_id"])

    @staticmethod
    async def _upsert_subcategory(session: AsyncSession, body: dict) -> None:
        subcategory_id = body["subcategory_id"]
        model = await session.get(SubCategoryModel, subcategory_id)
        if model is None:
            session.add(
                SubCategoryModel(
                    id=subcategory_id,
                    name=body["name"],
                    category_id=body["category_id"],
                    is_default=body.get("is_default", True),
                )
            )
            logger.info("Subcategory %s created in read copy", subcategory_id)
        else:
            model.name = body["name"]
            model.category_id = body["category_id"]
            model.is_default = body.get("is_default", True)
            logger.info("Subcategory %s updated in read copy", subcategory_id)

    @staticmethod
    async def _delete_subcategory(session: AsyncSession, body: dict) -> None:
        model = await session.get(SubCategoryModel, body["subcategory_id"])
        if model is None:
            logger.info("Subcategory %s already absent — no-op", body["subcategory_id"])
            return
        await session.delete(model)
        logger.info("Subcategory %s removed from read copy", body["subcategory_id"])

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
        routing_key = json.loads(original.body.decode("utf-8")).get("event_type", "category.updated")
        await exchange.publish(msg, routing_key=routing_key)


async def main() -> None:
    consumer = TaxonomySyncConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
