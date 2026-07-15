"""Consumer for transaction.categorized events from categorization-service.

Always overwrites the transaction's denormalized categorization fields
with cat-service's result.  Logs to stdout if the new result diverges
from an existing categorization (e.g. from a previous categorization run).

Atomicity: transaction update + inbox row committed in one DB transaction.
Idempotency: inbox pattern on (message_id, consumer_name) with UNIQUE constraint.

Connection/topology/retry/DLQ boilerplate lives in the shared
``messaging.ConsumerBase`` (max_retries=5 preserved).  Deduplication
deliberately does NOT use the base's ``InboxDeduplicator`` hook: the inbox
row must commit atomically with the transaction update, so it is written
inside ``handle``'s own DB transaction.

The stale-retry backoff is preserved: when the transaction row is not
persisted yet (categorized event raced ahead of the tx commit), ``handle``
sleeps ``2**retry_count`` seconds before raising, and the base's retry
ladder republishes with an incremented ``x-retry-count`` header.  The
inline sleep blocks this consumer only (prefetch=1) — same behavior as
the pre-shared implementation, observed load-bearing in live runs.

Run as a standalone process::

    python -m app.workers.categorized_consumer
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_pika.abc import AbstractIncomingMessage
from messaging import ConsumerBase, PoisonMessageError, setup_worker_logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models import CategoryModel, ProcessedEventModel, TransactionModel

logger = logging.getLogger(__name__)

QUEUE_NAME = "transaction_service.transaction_categorized"
ROUTING_KEY = "transaction.categorized"
MAX_RETRIES = 5
RETRY_HEADER = "x-retry-count"


class TransactionCategorizedConsumer(ConsumerBase):
    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEY,
            max_retries=MAX_RETRIES,
        )

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        message_id = payload.get("correlation_id", "")
        transaction_id = payload.get("transaction_id")

        if not transaction_id:
            raise PoisonMessageError("Missing transaction_id in event payload")

        async with async_session_factory() as session:
            if message_id and await self._is_duplicate(session, message_id):
                logger.info("Skipping duplicate (message_id=%s)", message_id)
                return

            tx = await self._get_transaction(session, transaction_id)
            if tx is None:
                await self._stale_backoff(message, transaction_id)
                raise _TransactionNotFoundYet(transaction_id)

            # v2 events carry the parent name; fall back to a local
            # lookup for v1/empty payloads.
            parent_name = payload.get("category_name") or None
            if parent_name is None:
                parent_name = await self._lookup_parent_name(session, payload.get("category_id"))
            self._apply_categorization(tx, payload, parent_name)

            if message_id:
                self._add_inbox_row(session, message_id, payload.get("event_type", ""))

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if "processed_events" in str(exc).lower() or "uq_processed_events" in str(exc).lower():
                    logger.info("Duplicate on commit (message_id=%s) — benign race", message_id)
                    return
                raise

    @staticmethod
    async def _stale_backoff(message: AbstractIncomingMessage, transaction_id: int) -> None:
        """Exponential wait before the base republishes a not-found-yet event."""
        retry_count = int((message.headers or {}).get(RETRY_HEADER, 0))
        if retry_count < MAX_RETRIES:
            delay = 2**retry_count
            logger.warning(
                "Transaction %s not found yet (retry=%d/%d, backoff=%ds)",
                transaction_id,
                retry_count + 1,
                MAX_RETRIES,
                delay,
            )
            await asyncio.sleep(delay)

    @staticmethod
    async def _lookup_parent_name(session: AsyncSession, category_id: int | None) -> str | None:
        """Resolve the parent category name from the local categories table.

        ``category_name`` on a transaction is always the parent-level name, so
        the consumer derives it from ``category_id`` rather than trusting the
        event's ``subcategory_name``.  Returns ``None`` if the id is unknown
        (e.g. categories table not yet synced), in which case the existing
        ``category_name`` is left untouched.
        """
        if category_id is None:
            return None
        cat = await session.get(CategoryModel, category_id)
        if cat is None:
            # category_id not in the local categories table (e.g. not yet
            # synced).  category_name is left stale while subcategory_name is
            # still updated — log it rather than diverging silently.
            logger.warning(
                "Cannot resolve parent name for category_id=%s — "
                "category_name left unchanged (categories table not synced?)",
                category_id,
            )
            return None
        return cat.name

    @staticmethod
    def _apply_categorization(
        tx: TransactionModel,
        event_data: dict,
        parent_name: str | None = None,
    ) -> None:
        new_sub = event_data.get("subcategory_id")
        new_tier = event_data.get("tier", "")
        new_confidence = event_data.get("confidence", "")
        new_category_id = event_data.get("category_id")
        # The event carries the SUB-level name; treat "" as absent.
        new_subcategory_name = event_data.get("subcategory_name", "") or None

        # Protect a manual user choice: auto-categorization must not silently
        # overwrite a category the user set themselves (tier == "manual").
        if tx.categorization_tier == "manual":
            logger.info(
                "Skipping auto-categorization for tx=%d: manual user choice preserved",
                tx.id,
            )
            return

        # category_name is ALWAYS the parent name; only override when resolved.
        target_category_name = parent_name if parent_name else tx.category_name

        if (
            tx.subcategory_id == new_sub
            and tx.categorization_tier == new_tier
            and tx.categorization_confidence == new_confidence
            and tx.category_name == target_category_name
            and (new_subcategory_name is None or tx.subcategory_name == new_subcategory_name)
            and (new_category_id is None or tx.category_id == new_category_id)
        ):
            return

        if tx.subcategory_id is not None and tx.subcategory_id != new_sub:
            logger.info(
                "Categorization divergence: tx=%d existing=(sub=%s,tier=%s) new=(sub=%s,tier=%s)",
                tx.id,
                tx.subcategory_id,
                tx.categorization_tier,
                new_sub,
                new_tier,
            )

        tx.subcategory_id = new_sub
        tx.categorization_tier = new_tier
        tx.categorization_confidence = new_confidence
        if new_category_id is not None:
            tx.category_id = new_category_id
        # category_name = parent name (NOT the subcategory name).
        if parent_name:
            tx.category_name = parent_name
        # subcategory_name = the sub-level name from the event.
        if new_subcategory_name is not None:
            tx.subcategory_name = new_subcategory_name

    @staticmethod
    async def _get_transaction(session: AsyncSession, transaction_id: int) -> TransactionModel | None:
        stmt = select(TransactionModel).where(TransactionModel.id == transaction_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

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


class _TransactionNotFoundYet(Exception):
    def __init__(self, transaction_id: int) -> None:
        self.transaction_id = transaction_id
        super().__init__(f"Transaction {transaction_id} not persisted yet")


async def main() -> None:
    setup_worker_logging(__name__)
    await TransactionCategorizedConsumer().run()


if __name__ == "__main__":
    asyncio.run(main())
