"""Outbox publisher worker — polls outbox_events and publishes to RabbitMQ.

Run as a standalone process::

    python -m app.workers.outbox_publisher

Uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so multiple worker instances
can run concurrently without double-publishing. Events are delivered
at-least-once; downstream consumers must be idempotent.

This worker uses asyncpg (async) for DB polling, independent of the
main API's sync psycopg2 engine.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import NoReturn

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"
POLL_INTERVAL_S = 2.0
BATCH_SIZE = 20
MAX_BACKOFF_S = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OutboxPublisherWorker:
    """Polls the outbox table and publishes pending events to RabbitMQ."""

    def __init__(
        self,
        database_url: str,
        rabbitmq_url: str,
        poll_interval: float = POLL_INTERVAL_S,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self._database_url = database_url
        self._rabbitmq_url = rabbitmq_url
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._engine = None
        self._session_factory = None
        self._connection = None
        self._channel = None
        self._exchange = None

    async def connect(self) -> None:
        self._engine = create_async_engine(self._database_url, pool_size=2)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

        self._connection = await aio_pika.connect_robust(self._rabbitmq_url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
        )
        logger.info("Connected to RabbitMQ exchange=%s", EXCHANGE_NAME)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
        if self._engine:
            await self._engine.dispose()

    async def run_forever(self) -> NoReturn:
        logger.info(
            "Outbox publisher started (poll=%.1fs, batch=%d)",
            self._poll_interval,
            self._batch_size,
        )
        while True:
            published = await self._process_batch()
            if published == 0:
                await asyncio.sleep(self._poll_interval)

    async def _process_batch(self) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                rows = (
                    await session.execute(
                        text(
                            "SELECT id, event_type, payload_json, correlation_id, attempts "
                            "FROM outbox_events "
                            "WHERE status IN ('pending', 'failed') "
                            "  AND next_attempt_at <= :now "
                            "ORDER BY created_at "
                            "LIMIT :batch "
                            "FOR UPDATE SKIP LOCKED"
                        ),
                        {"now": _utcnow(), "batch": self._batch_size},
                    )
                ).fetchall()

                if not rows:
                    return 0

                for row in rows:
                    await self._try_publish(session, row)

            return len(rows)

    async def _try_publish(self, session: AsyncSession, row) -> None:
        event_id, event_type, payload_json, correlation_id, attempts = row
        try:
            message = Message(
                body=payload_json.encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await self._exchange.publish(message, routing_key=event_type)

            await session.execute(
                text(
                    "UPDATE outbox_events SET status = 'published', published_at = :now "
                    "WHERE id = :id"
                ),
                {"now": _utcnow(), "id": event_id},
            )
            logger.info(
                "Published %s (id=%s, correlation=%s)",
                event_type,
                event_id,
                correlation_id,
            )
        except Exception:
            backoff = min(2 ** attempts * 5, MAX_BACKOFF_S)
            next_at = _utcnow() + timedelta(seconds=backoff)
            await session.execute(
                text(
                    "UPDATE outbox_events SET status = 'failed', "
                    "attempts = attempts + 1, next_attempt_at = :next_at "
                    "WHERE id = :id"
                ),
                {"next_at": next_at, "id": event_id},
            )
            logger.warning(
                "Failed to publish %s (id=%s, attempt=%d, next_retry=%s)",
                event_type,
                event_id,
                attempts + 1,
                next_at.isoformat(),
                exc_info=True,
            )


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    rabbitmq_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    if not database_url:
        raise RuntimeError("DATABASE_URL must be set (use asyncpg driver)")

    worker = OutboxPublisherWorker(database_url, rabbitmq_url)
    await worker.connect()

    try:
        await worker.run_forever()
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
