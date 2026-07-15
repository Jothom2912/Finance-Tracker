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

Connection/topology/retry/DLQ boilerplate lives in the shared
``messaging.ConsumerBase`` (max_retries=5 preserved).  Deduplication
deliberately does NOT use the base's ``InboxDeduplicator`` hook: the inbox
row must commit atomically with the read-copy write, so it is written
inside ``handle``'s own DB transaction.

Run as a standalone process::

    python -m app.workers.taxonomy_sync_consumer
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_pika.abc import AbstractIncomingMessage
from messaging import ConsumerBase, setup_worker_logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models import CategoryModel, ProcessedEventModel, SubCategoryModel

logger = logging.getLogger(__name__)

QUEUE_NAME = "transaction_service.taxonomy_sync"
ROUTING_KEYS = ("category.*", "subcategory.*")
MAX_RETRIES = 5


class TaxonomySyncConsumer(ConsumerBase):
    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEYS,
            max_retries=MAX_RETRIES,
        )

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        message_id = payload.get("correlation_id", "")
        event_type = payload.get("event_type", "")

        async with async_session_factory() as session:
            if message_id and await self._is_duplicate(session, message_id):
                logger.info("Skipping duplicate (message_id=%s)", message_id)
                return

            handled = await self._dispatch(session, event_type, payload)
            if not handled:
                logger.warning("Unknown event_type %r — acking without action", event_type)
                return

            if message_id:
                self._add_inbox_row(session, message_id, event_type)

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if "processed_events" in str(exc).lower() or "uq_processed_events" in str(exc).lower():
                    logger.info("Duplicate on commit (message_id=%s) — benign race", message_id)
                    return
                raise

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


async def main() -> None:
    setup_worker_logging(__name__)
    await TaxonomySyncConsumer().run()


if __name__ == "__main__":
    asyncio.run(main())
