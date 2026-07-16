"""Outbox publisher worker — polls ``outbox_events`` and publishes to RabbitMQ.

Consolidates the eight per-service ``app/workers/outbox_publisher.py``
copies.  Semantics are a superset of the copies:

* Same poll loop, batch size, backoff formula and message shape
  (persistent, ``content_type='application/json'``, routing key =
  ``event_type``).
* NEW: the loop body is wrapped in try/except — a transient DB or broker
  error is logged and retried instead of killing the process (the copies
  crashed and relied on container restart).
* NEW: per-entry commit (default) — each entry is fetched, published and
  committed in its own transaction, so a crash mid-batch never loses the
  publish marks of earlier entries.  ``commit_per_entry=False`` restores
  the legacy fetch-batch/commit-once behaviour.
* NEW: optional ``max_attempts`` — exhausted entries are marked
  ``'dead'`` instead of retrying forever.
* NEW: optional periodic ``purge_published_after_days`` housekeeping.

Typical service ``__main__`` shim::

    worker = OutboxPublisherWorker(
        session_factory=async_session_factory,
        repository_or_model=OutboxEventModel,
        rabbitmq_url=settings.RABBITMQ_URL,
    )
    asyncio.run(worker.run_forever())
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, NoReturn, Protocol

from aio_pika import DeliveryMode, Message
from sqlalchemy.ext.asyncio import AsyncSession

from messaging.outbox import OutboxEntry, OutboxEventMixin, OutboxRepository
from messaging.rabbitmq import EXCHANGE_NAME, RabbitMQPublisher

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 2.0
BATCH_SIZE = 20
ERROR_BACKOFF_S = 5.0
PURGE_INTERVAL_S = 3600.0


class RawPublisher(Protocol):
    """Anything that can publish a pre-built message (see RabbitMQPublisher)."""

    async def publish_raw(self, message: Message, routing_key: str) -> None: ...


class OutboxRepositoryLike(Protocol):
    """Structural type for repository factories (custom repos welcome)."""

    async def fetch_pending(self, batch_size: int = ...) -> list[OutboxEntry]: ...
    async def mark_published(self, event_id: str) -> None: ...
    async def record_failure(self, entry: OutboxEntry, *, max_attempts: int | None = ...) -> object: ...


RepositoryFactory = Callable[[AsyncSession], OutboxRepositoryLike]


class OutboxPublisherWorker:
    """Polls the outbox table and publishes pending events to RabbitMQ.

    Backoff on failure uses ``min(2**attempts * 5, MAX_BACKOFF_S)``
    seconds — capped at 5 minutes (same formula as the legacy copies).

    ``repository_or_model`` accepts either the service's outbox model
    class (an ``OutboxRepository`` is created per session) or a callable
    ``session -> repository`` for services with a custom repository.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        repository_or_model: type[OutboxEventMixin] | RepositoryFactory,
        rabbitmq_url: str | None = None,
        exchange_name: str = EXCHANGE_NAME,
        poll_interval: float = POLL_INTERVAL_S,
        batch_size: int = BATCH_SIZE,
        max_attempts: int | None = None,
        *,
        commit_per_entry: bool = True,
        purge_published_after_days: int | None = None,
        purge_interval: float = PURGE_INTERVAL_S,
        error_backoff: float = ERROR_BACKOFF_S,
        publisher: RawPublisher | None = None,
    ) -> None:
        if rabbitmq_url is None and publisher is None:
            raise ValueError("Provide rabbitmq_url or an already-connected publisher")

        self._session_factory = session_factory
        if isinstance(repository_or_model, type):
            model = repository_or_model
            self._repo_factory: RepositoryFactory = lambda session: OutboxRepository(session, model)
        else:
            self._repo_factory = repository_or_model

        self._rabbitmq_url = rabbitmq_url
        self._exchange_name = exchange_name
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._commit_per_entry = commit_per_entry
        self._purge_after_days = purge_published_after_days
        self._purge_interval = purge_interval
        self._error_backoff = error_backoff
        self._publisher = publisher
        self._owns_publisher = publisher is None
        self._last_purge_monotonic: float | None = None

    async def run_forever(self) -> NoReturn:
        """Poll-publish loop; transient errors are logged and retried."""
        logger.info(
            "Outbox publisher started (exchange=%s, poll=%.1fs, batch=%d, max_attempts=%s)",
            self._exchange_name,
            self._poll_interval,
            self._batch_size,
            self._max_attempts,
        )
        while True:
            try:
                await self._ensure_publisher()
                published = await self._process_batch()
                await self._maybe_purge()
            except Exception:
                logger.exception("Outbox batch failed — retrying in %.1fs", self._error_backoff)
                await asyncio.sleep(self._error_backoff)
                continue
            if published == 0:
                await asyncio.sleep(self._poll_interval)

    async def close(self) -> None:
        """Close the publisher connection if this worker created it."""
        if self._owns_publisher and isinstance(self._publisher, RabbitMQPublisher):
            await self._publisher.close()

    async def _ensure_publisher(self) -> RawPublisher:
        if self._publisher is None:
            assert self._rabbitmq_url is not None  # guarded in __init__
            publisher = RabbitMQPublisher(self._rabbitmq_url, self._exchange_name)
            await publisher.connect()
            self._publisher = publisher
        return self._publisher

    async def _process_batch(self) -> int:
        if self._commit_per_entry:
            return await self._process_batch_per_entry()
        return await self._process_batch_legacy()

    async def _process_batch_per_entry(self) -> int:
        """One transaction per entry: fetch(1) → publish → commit.

        The row lock is held until its own commit, so concurrent workers
        still cannot double-publish, and a crash mid-batch keeps every
        already-committed publish mark.
        """
        processed = 0
        for _ in range(self._batch_size):
            async with self._session_factory() as session:
                repo = self._repo_factory(session)
                entries = await repo.fetch_pending(batch_size=1)
                if not entries:
                    break
                await self._try_publish(repo, entries[0])
                await session.commit()
                processed += 1
        return processed

    async def _process_batch_legacy(self) -> int:
        """Legacy behaviour: fetch a whole batch, commit once at the end."""
        async with self._session_factory() as session:
            repo = self._repo_factory(session)
            entries = await repo.fetch_pending(batch_size=self._batch_size)
            if not entries:
                return 0

            for entry in entries:
                await self._try_publish(repo, entry)

            await session.commit()
            return len(entries)

    async def _try_publish(
        self,
        repo: OutboxRepositoryLike,
        entry: OutboxEntry,
    ) -> None:
        try:
            message = Message(
                body=entry.payload_json.encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            assert self._publisher is not None  # _ensure_publisher ran first
            await self._publisher.publish_raw(message, routing_key=entry.event_type)
            await repo.mark_published(entry.id)
            logger.info(
                "Published %s (id=%s, correlation=%s)",
                entry.event_type,
                entry.id,
                entry.correlation_id,
            )
        except Exception:
            next_at = await repo.record_failure(entry, max_attempts=self._max_attempts)
            if next_at is None and self._max_attempts is not None:
                logger.error(
                    "Giving up on %s (id=%s) after %d attempts — marked dead",
                    entry.event_type,
                    entry.id,
                    entry.attempts + 1,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Failed to publish %s (id=%s, attempt=%d, next_retry=%s)",
                    entry.event_type,
                    entry.id,
                    entry.attempts + 1,
                    next_at,
                    exc_info=True,
                )

    async def _maybe_purge(self) -> None:
        if self._purge_after_days is None:
            return
        now = time.monotonic()
        if self._last_purge_monotonic is not None and now - self._last_purge_monotonic < self._purge_interval:
            return
        self._last_purge_monotonic = now
        async with self._session_factory() as session:
            repo = self._repo_factory(session)
            purge = getattr(repo, "purge_published", None)
            if purge is None:
                return
            deleted = await purge(older_than_days=self._purge_after_days)
            await session.commit()
        if deleted:
            logger.info(
                "Purged %d published outbox rows older than %d days",
                deleted,
                self._purge_after_days,
            )
