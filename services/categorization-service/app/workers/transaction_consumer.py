"""Consumer for transaction.created events.

Listens on RabbitMQ, runs the full categorization pipeline
(rules -> ML -> LLM -> fallback), persists audit trail in
categorization_results, and emits transaction.categorized via outbox.

All three writes (categorization_results, outbox_events, processed_events)
happen in a single DB transaction.  This guarantees atomicity: either all
three are committed, or none are.  The UNIQUE constraint on
(message_id, consumer_name) in processed_events is the last line of
defense against duplicates — even if two consumer instances race on the
same message, one will fail with IntegrityError and roll back.

Run as a standalone process::

    python -m app.workers.transaction_consumer
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage
from contracts.events.transaction import TransactionCategorizedEvent
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_outbox_repository import PostgresOutboxRepository
from app.adapters.outbound.postgres_result_repository import PostgresCategorizationResultRepository
from app.adapters.outbound.rule_engine import RuleEngine
from app.config import settings
from app.database import async_session_factory
from app.domain.entities import CategorizationResultRecord
from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS
from app.domain.value_objects import CategorizationResult, CategorizationTier, Confidence
from app.models import CategoryModel, ProcessedEventModel, SubCategoryModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "categorization.transaction_created"
ROUTING_KEY = "transaction.created"
MODEL_VERSION = "rules-keyword-v1"
MAX_RETRIES = 3
CLEANUP_DAYS = 30
_CLEANUP_SAFETY_THRESHOLD = 0.9


class TransactionCreatedConsumer:
    """Async consumer for transaction.created events.

    Uses inbox pattern (processed_events table) for deduplication.
    All writes (result + outbox + inbox) committed in one DB transaction.
    """

    def __init__(self, rule_engine: RuleEngine, fallback_sub_id: int, fallback_cat_id: int) -> None:
        self._rule_engine = rule_engine
        self._fallback_sub_id = fallback_sub_id
        self._fallback_cat_id = fallback_cat_id
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None

    async def run(self) -> None:
        await self._cleanup_old_inbox_rows()
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
                    logger.info("Skipping duplicate (message_id=%s)", message_id)
                    await message.ack()
                    return

                await self._handle(session, body)

                if message_id:
                    self._add_inbox_row(session, message_id, event_type)

                try:
                    await session.commit()
                except IntegrityError as exc:
                    await session.rollback()
                    if "processed_events" in str(exc).lower() or "uq_processed_events" in str(exc).lower():
                        logger.info(
                            "Duplicate detected on commit (message_id=%s) — benign race, acking",
                            message_id,
                        )
                        await message.ack()
                        return
                    raise

            await message.ack()

        except Exception:
            retry_count = int((message.headers or {}).get("x-retry-count", 0))
            if retry_count < MAX_RETRIES:
                logger.warning(
                    "Handler failed (retry=%d/%d) — republishing",
                    retry_count + 1,
                    MAX_RETRIES,
                    exc_info=True,
                )
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error("Max retries reached — sending to DLQ", exc_info=True)
                await message.nack(requeue=False)

    async def _handle(self, session: AsyncSession, event_data: dict) -> None:
        """Run pipeline and write result + outbox within the caller's session."""
        transaction_id = event_data.get("transaction_id")
        description = event_data.get("description", "")
        amount_str = event_data.get("amount", "0")
        amount = float(amount_str)

        result = self._categorize(description, amount)

        result_repo = PostgresCategorizationResultRepository(session)
        outbox_repo = PostgresOutboxRepository(session)

        await result_repo.save(
            CategorizationResultRecord(
                id=None,
                transaction_id=transaction_id,
                category_id=result.category_id,
                subcategory_id=result.subcategory_id,
                merchant_id=result.merchant_id,
                tier=result.tier,
                confidence=result.confidence,
                model_version=MODEL_VERSION,
            ),
        )

        await outbox_repo.add(
            event=TransactionCategorizedEvent(
                transaction_id=transaction_id,
                category_id=result.category_id,
                subcategory_id=result.subcategory_id,
                merchant_id=result.merchant_id,
                tier=result.tier.value,
                confidence=result.confidence.value,
                model_version=MODEL_VERSION,
            ),
            aggregate_type="transaction",
            aggregate_id=str(transaction_id),
        )

        logger.info(
            "Categorized transaction %s -> cat=%d, sub=%d, tier=%s [%s]",
            transaction_id,
            result.category_id,
            result.subcategory_id,
            result.tier.value,
            result.confidence.value,
        )

    def _categorize(self, description: str, amount: float) -> CategorizationResult:
        result = self._rule_engine.match(description, amount)
        if result is not None:
            return result

        return CategorizationResult(
            category_id=self._fallback_cat_id,
            subcategory_id=self._fallback_sub_id,
            tier=CategorizationTier.FALLBACK,
            confidence=Confidence.LOW,
        )

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
        """Add inbox row to the current session (committed by caller)."""
        session.add(
            ProcessedEventModel(
                message_id=message_id,
                consumer_name=QUEUE_NAME,
                event_type=event_type,
            ),
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
        await exchange.publish(msg, routing_key=ROUTING_KEY)

    async def _cleanup_old_inbox_rows(self) -> None:
        async with async_session_factory() as session:
            try:
                total = await session.scalar(
                    select(func.count()).select_from(ProcessedEventModel),
                )
                cutoff_stmt = (
                    select(func.count())
                    .select_from(ProcessedEventModel)
                    .where(
                        ProcessedEventModel.processed_at < text(f"NOW() - INTERVAL '{CLEANUP_DAYS} days'"),
                    )
                )
                to_delete = await session.scalar(cutoff_stmt)

                if total and total > 0 and to_delete and to_delete / total > _CLEANUP_SAFETY_THRESHOLD:
                    logger.warning(
                        "Inbox cleanup would delete >%.0f%% of rows (%d/%d), aborting — check container clock",
                        _CLEANUP_SAFETY_THRESHOLD * 100,
                        to_delete,
                        total,
                    )
                    return

                result = await session.execute(
                    delete(ProcessedEventModel).where(
                        ProcessedEventModel.processed_at < text(f"NOW() - INTERVAL '{CLEANUP_DAYS} days'"),
                    ),
                )
                await session.commit()
                deleted = result.rowcount
                if deleted:
                    logger.info("Inbox cleanup: removed %d rows older than %d days", deleted, CLEANUP_DAYS)
            except Exception:
                await session.rollback()
                logger.warning("Inbox cleanup failed — will retry next restart", exc_info=True)


async def _build_rule_engine() -> tuple[RuleEngine, int, int]:
    """Build rule engine from DB data at startup."""
    async with async_session_factory() as session:
        cat_rows = await session.execute(select(CategoryModel))
        cats = cat_rows.scalars().all()
        cat_ids = {c.id for c in cats}

        sub_rows = await session.execute(select(SubCategoryModel))
        subs = sub_rows.scalars().all()

        subcategory_lookup: dict[str, tuple[int, int]] = {}
        for sub in subs:
            if sub.category_id in cat_ids:
                subcategory_lookup[sub.name] = (sub.id, sub.category_id)

    keyword_mappings = [(kw, mapping["subcategory"]) for kw, mapping in SEED_MERCHANT_MAPPINGS.items()]
    engine = RuleEngine(keyword_mappings=keyword_mappings, subcategory_lookup=subcategory_lookup)

    fallback = subcategory_lookup.get("Anden", (0, 0))
    return engine, fallback[0], fallback[1]


async def main() -> None:
    rule_engine, fallback_sub, fallback_cat = await _build_rule_engine()
    consumer = TransactionCreatedConsumer(rule_engine, fallback_sub, fallback_cat)
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
