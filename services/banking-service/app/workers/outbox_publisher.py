"""Outbox publisher worker — thin shim over finans-tracker-messaging.

Run as a standalone process::

    python -m app.workers.outbox_publisher

All poll/publish/backoff logic lives in ``messaging.OutboxPublisherWorker``
(same exchange ``finans_tracker.events``, routing key = ``event_type``,
persistent JSON messages, ``min(2**attempts * 5, 300)`` backoff).
"""

from __future__ import annotations

import asyncio

from messaging import OutboxPublisherWorker, setup_worker_logging

from app.config import settings
from app.database import async_session_factory
from app.models.outbox import OutboxEventModel


async def main() -> None:
    setup_worker_logging(__name__)
    worker = OutboxPublisherWorker(
        session_factory=async_session_factory,
        repository_or_model=OutboxEventModel,
        rabbitmq_url=settings.RABBITMQ_URL,
    )
    try:
        await worker.run_forever()
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
