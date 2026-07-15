"""Outbox publisher worker — thin shim over finans-tracker-messaging.

Run as a standalone process::

    python -m app.workers.outbox_publisher

All poll/publish/backoff logic lives in ``messaging.OutboxPublisherWorker``
(same exchange ``finans_tracker.events``, routing key = ``event_type``,
persistent JSON messages, ``min(2**attempts * 5, 300)`` backoff).

This worker uses asyncpg (async) for DB polling, independent of the main
API's sync psycopg2 engine — DATABASE_URL must use the asyncpg driver
(same contract as before the shared-package migration).
"""

from __future__ import annotations

import asyncio
import os

from messaging import OutboxPublisherWorker, setup_worker_logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.outbox import OutboxEventModel


async def main() -> None:
    setup_worker_logging(__name__)

    database_url = os.environ.get("DATABASE_URL", "")
    rabbitmq_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set (use asyncpg driver)")

    engine = create_async_engine(database_url, pool_size=2)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    worker = OutboxPublisherWorker(
        session_factory=session_factory,
        repository_or_model=OutboxEventModel,
        rabbitmq_url=rabbitmq_url,
    )
    try:
        await worker.run_forever()
    finally:
        await worker.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
