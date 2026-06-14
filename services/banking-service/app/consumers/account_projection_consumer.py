"""Consumer that keeps accounts_projection in sync with account-service events.

Listens on account.created and account.updated, upserts into accounts_projection.
This projection is used by start_sync_saga for account_name enrichment.

Normalizes the field name inconsistency between events:
  - AccountCreatedEvent has ``account_name``
  - AccountUpdatedEvent has ``name``

Run as a standalone process::

    python -m app.consumers.account_projection_consumer
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

from app.adapters.outbound.postgres_account_projection_repository import (
    PostgresAccountProjectionRepository,
)
from app.config import settings
from app.database import async_session_factory
from app.models.processed_events import ProcessedEventModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "banking.account_sync"
ROUTING_KEYS = ["account.created", "account.updated"]
MAX_RETRIES = 3


class AccountProjectionConsumer:
    def __init__(self) -> None:
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None

    async def run(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

        exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.TOPIC, durable=True,
        )

        dlx = await self._channel.declare_exchange(
            f"{EXCHANGE_NAME}.dlx", ExchangeType.DIRECT, durable=True,
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
        for key in ROUTING_KEYS:
            await queue.bind(exchange, routing_key=key)

        await queue.consume(self._on_message)
        logger.info(
            "Consumer %s listening on %s", QUEUE_NAME, ROUTING_KEYS,
        )
        await asyncio.Future()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        correlation_id = body.get("correlation_id", "")

        try:
            async with async_session_factory() as session:
                if correlation_id and await self._is_duplicate(session, correlation_id):
                    logger.info("Skipping duplicate (correlation_id=%s)", correlation_id)
                    await message.ack()
                    return

                account_id = body["account_id"]
                user_id = body["user_id"]
                account_name = body.get("account_name") or body.get("name", "Unknown")

                repo = PostgresAccountProjectionRepository(session)
                await repo.upsert(account_id, user_id, account_name)

                if correlation_id:
                    session.add(ProcessedEventModel(
                        correlation_id=correlation_id,
                        consumer_name=QUEUE_NAME,
                    ))

                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    logger.info(
                        "Duplicate on commit (correlation_id=%s) — benign race",
                        correlation_id,
                    )
                    await message.ack()
                    return

            logger.info(
                "Upserted account projection: account_id=%d, name=%s",
                account_id,
                account_name,
            )
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

    @staticmethod
    async def _is_duplicate(session: AsyncSession, correlation_id: str) -> bool:
        result = await session.execute(
            select(ProcessedEventModel).where(
                ProcessedEventModel.correlation_id == correlation_id,
                ProcessedEventModel.consumer_name == QUEUE_NAME,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _republish(self, original: AbstractIncomingMessage, retry_count: int) -> None:
        assert self._channel is not None
        exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.TOPIC, durable=True,
        )
        headers = dict(original.headers or {})
        headers["x-retry-count"] = retry_count
        msg = aio_pika.Message(
            body=original.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        await exchange.publish(msg, routing_key=original.routing_key or "account.created")


async def main() -> None:
    consumer = AccountProjectionConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
