"""Consumer for transaction.categorized events from categorization-service.

Always overwrites the transaction's denormalized categorization fields
with cat-service's result.  Logs to stdout if the new result diverges
from an existing categorization (e.g. from the monolith's rule engine
during dual-run).

Atomicity: transaction update + inbox row committed in one DB transaction.
Idempotency: inbox pattern on (message_id, consumer_name) with UNIQUE constraint.

Run as a standalone process::

    python -m app.workers.categorized_consumer
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
from app.models import ProcessedEventModel, TransactionModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "transaction_service.transaction_categorized"
ROUTING_KEY = "transaction.categorized"
MAX_RETRIES = 5


class TransactionCategorizedConsumer:
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
        transaction_id = body.get("transaction_id")

        if not transaction_id:
            logger.error("Missing transaction_id in event payload")
            await message.nack(requeue=False)
            return

        try:
            async with async_session_factory() as session:
                if message_id and await self._is_duplicate(session, message_id):
                    logger.info("Skipping duplicate (message_id=%s)", message_id)
                    await message.ack()
                    return

                tx = await self._get_transaction(session, transaction_id)
                if tx is None:
                    raise _TransactionNotFoundYet(transaction_id)

                self._apply_categorization(tx, body)

                if message_id:
                    self._add_inbox_row(session, message_id, body.get("event_type", ""))

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

        except _TransactionNotFoundYet:
            retry_count = int((message.headers or {}).get("x-retry-count", 0))
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
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error(
                    "Transaction %s not found after %d retries — DLQ",
                    transaction_id,
                    MAX_RETRIES,
                )
                await message.nack(requeue=False)

        except Exception:
            retry_count = int((message.headers or {}).get("x-retry-count", 0))
            if retry_count < MAX_RETRIES:
                logger.warning(
                    "Handler failed (retry=%d/%d)",
                    retry_count + 1,
                    MAX_RETRIES,
                    exc_info=True,
                )
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error("Max retries reached — DLQ", exc_info=True)
                await message.nack(requeue=False)

    @staticmethod
    def _apply_categorization(tx: TransactionModel, event_data: dict) -> None:
        new_sub = event_data.get("subcategory_id")
        new_tier = event_data.get("tier", "")
        new_confidence = event_data.get("confidence", "")

        if (
            tx.subcategory_id == new_sub
            and tx.categorization_tier == new_tier
            and tx.categorization_confidence == new_confidence
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


class _TransactionNotFoundYet(Exception):
    def __init__(self, transaction_id: int) -> None:
        self.transaction_id = transaction_id
        super().__init__(f"Transaction {transaction_id} not persisted yet")


async def main() -> None:
    consumer = TransactionCategorizedConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
