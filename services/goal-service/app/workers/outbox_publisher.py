from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from aio_pika import DeliveryMode, Message
from app.adapters.outbound.postgres_outbox_repository import PostgresOutboxRepository
from app.adapters.outbound.rabbitmq_publisher import RabbitMQPublisher
from app.config import settings
from app.database import async_session_factory
from app.domain.entities import OutboxEntry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 2.0
BATCH_SIZE = 20
MAX_BACKOFF_S = 300


class OutboxPublisherWorker:
    def __init__(
        self, publisher: RabbitMQPublisher, poll_interval: float = POLL_INTERVAL_S, batch_size: int = BATCH_SIZE
    ) -> None:
        self._publisher = publisher
        self._poll_interval = poll_interval
        self._batch_size = batch_size

    async def run_forever(self) -> NoReturn:
        logger.info("Goal outbox publisher started (poll=%.1fs, batch=%d)", self._poll_interval, self._batch_size)
        while True:
            published = await self._process_batch()
            if published == 0:
                await asyncio.sleep(self._poll_interval)

    async def _process_batch(self) -> int:
        async with async_session_factory() as session:
            repo = PostgresOutboxRepository(session)
            entries = await repo.fetch_pending(batch_size=self._batch_size)
            if not entries:
                return 0
            for entry in entries:
                await self._try_publish(repo, entry)
            await session.commit()
            return len(entries)

    async def _try_publish(self, repo: PostgresOutboxRepository, entry: OutboxEntry) -> None:
        try:
            message = Message(
                body=entry.payload_json.encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await self._publisher.publish_raw(message, routing_key=entry.event_type)
            await repo.mark_published(entry.id)
        except Exception:
            backoff = min(2**entry.attempts * 5, MAX_BACKOFF_S)
            next_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=backoff)
            await repo.mark_failed(entry.id, next_at)
            logger.warning("Failed to publish %s (id=%s)", entry.event_type, entry.id, exc_info=True)


async def main() -> None:
    publisher = RabbitMQPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    try:
        worker = OutboxPublisherWorker(publisher)
        await worker.run_forever()
    finally:
        await publisher.close()


if __name__ == "__main__":
    asyncio.run(main())
