"""Transactional outbox: declarative model mixin + async repository.

Consolidates the per-service ``OutboxEventModel`` / outbox repository
copies.  SQL predicates match the existing copies exactly so migration
is drop-in:

* ``fetch_pending``: ``status IN ('pending', 'failed') AND
  next_attempt_at <= now`` ordered by ``created_at``, limited, with
  ``FOR UPDATE SKIP LOCKED``.
* ``mark_failed``: ``status='failed', attempts=attempts+1,
  next_attempt_at=<given>``.
* Backoff formula: ``min(2**attempts * 5, 300)`` seconds.

Additions over the copies:

* ``add_batch`` — insert several events in one flush.
* ``record_failure`` — computes the backoff internally and, when
  ``max_attempts`` is reached, parks the entry in the new terminal
  status ``'dead'`` instead of retrying forever.
* ``purge_published`` — housekeeping for old published rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable
from uuid import uuid4

from sqlalchemy import Index, Integer, String, Text, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from messaging.rabbitmq import SerializableEvent
from messaging.time import utcnow_naive

#: Backoff formula constants — identical to every existing worker copy.
BACKOFF_BASE_S = 5
MAX_BACKOFF_S = 300


class OutboxStatus:
    """Outbox row lifecycle states (stored as plain strings)."""

    PENDING = "pending"
    FAILED = "failed"
    PUBLISHED = "published"
    #: Terminal state: gave up after ``max_attempts`` publish failures.
    #: New — the legacy copies retried forever.
    DEAD = "dead"


def compute_backoff(attempts: int, *, base_s: int = BACKOFF_BASE_S, cap_s: int = MAX_BACKOFF_S) -> int:
    """``min(2**attempts * 5, 300)`` seconds — the existing formula."""
    return min(2**attempts * base_s, cap_s)


class OutboxEventMixin:
    """Declarative mixin providing the standard ``outbox_events`` columns.

    Usage in a service::

        class OutboxEventModel(OutboxEventMixin, Base):
            pass

    A service may override individual columns (e.g. a wider
    ``correlation_id``) by redeclaring them on the concrete class.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=OutboxStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Index, ...]:
        return (
            Index(
                "ix_outbox_pending_poll",
                "status",
                "next_attempt_at",
                "created_at",
            ),
        )


@dataclass(frozen=True, slots=True)
class OutboxEntry:
    """Transport-agnostic snapshot of an outbox row."""

    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: str
    correlation_id: str | None
    status: str
    attempts: int
    next_attempt_at: datetime
    created_at: datetime


class OutboxRepository:
    """Async outbox repository bound to a service-specific model class.

    ``model`` is any declarative class with the ``OutboxEventMixin``
    columns — typically ``class OutboxEventModel(OutboxEventMixin, Base)``,
    but an existing hand-rolled model with the same columns works too.
    """

    def __init__(self, session: AsyncSession, model: type[OutboxEventMixin]) -> None:
        self._session = session
        self._model = model

    async def add(
        self,
        event: SerializableEvent,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None:
        self._session.add(self._build(event, aggregate_type, aggregate_id))
        await self._session.flush()

    async def add_batch(
        self,
        events: Iterable[SerializableEvent],
        aggregate_type: str,
        aggregate_id: str,
    ) -> None:
        """Insert several events for one aggregate in a single flush."""
        self._session.add_all(
            self._build(event, aggregate_type, aggregate_id) for event in events
        )
        await self._session.flush()

    async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]:
        """Fetch due pending/failed rows, locked with ``SKIP LOCKED``.

        On PostgreSQL this uses ``FOR UPDATE SKIP LOCKED`` so multiple
        workers never double-publish.  The SQLite dialect silently drops
        the FOR UPDATE clause, so tests running on sqlite exercise the
        query shape but not the locking.
        """
        now = utcnow_naive()
        stmt = (
            select(self._model)
            .where(
                self._model.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
                self._model.next_attempt_at <= now,
            )
            .order_by(self._model.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return [self._to_entry(m) for m in result.scalars().all()]

    async def mark_published(self, event_id: str) -> None:
        stmt = (
            update(self._model)
            .where(self._model.id == event_id)
            .values(
                status=OutboxStatus.PUBLISHED,
                published_at=utcnow_naive(),
            )
        )
        await self._session.execute(stmt)

    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None:
        """Legacy-compatible failure mark: status='failed', attempts+1."""
        stmt = (
            update(self._model)
            .where(self._model.id == event_id)
            .values(
                status=OutboxStatus.FAILED,
                attempts=self._model.attempts + 1,
                next_attempt_at=next_attempt_at,
            )
        )
        await self._session.execute(stmt)

    async def record_failure(
        self,
        entry: OutboxEntry,
        *,
        max_attempts: int | None = None,
    ) -> datetime | None:
        """Record a publish failure with the standard backoff.

        Returns the next attempt time, or ``None`` when the entry has
        exhausted ``max_attempts`` and was marked ``'dead'`` (terminal —
        no longer picked up by ``fetch_pending``).  With
        ``max_attempts=None`` behaviour matches the legacy copies:
        retry forever.
        """
        if max_attempts is not None and entry.attempts + 1 >= max_attempts:
            stmt = (
                update(self._model)
                .where(self._model.id == entry.id)
                .values(
                    status=OutboxStatus.DEAD,
                    attempts=self._model.attempts + 1,
                )
            )
            await self._session.execute(stmt)
            return None

        next_at = utcnow_naive() + timedelta(seconds=compute_backoff(entry.attempts))
        await self.mark_failed(entry.id, next_at)
        return next_at

    async def purge_published(self, older_than_days: int = 7) -> int:
        """Delete published rows older than the cutoff. Returns row count."""
        cutoff = utcnow_naive() - timedelta(days=older_than_days)
        stmt = delete(self._model).where(
            self._model.status == OutboxStatus.PUBLISHED,
            self._model.published_at < cutoff,
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)

    def _build(
        self,
        event: SerializableEvent,
        aggregate_type: str,
        aggregate_id: str,
    ) -> OutboxEventMixin:
        return self._model(
            id=str(uuid4()),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event.event_type,
            payload_json=event.to_json(),
            correlation_id=getattr(event, "correlation_id", None),
            status=OutboxStatus.PENDING,
            attempts=0,
        )

    @staticmethod
    def _to_entry(model: OutboxEventMixin) -> OutboxEntry:
        return OutboxEntry(
            id=model.id,
            aggregate_type=model.aggregate_type,
            aggregate_id=model.aggregate_id,
            event_type=model.event_type,
            payload_json=model.payload_json,
            correlation_id=model.correlation_id,
            status=model.status,
            attempts=model.attempts,
            next_attempt_at=model.next_attempt_at,
            created_at=model.created_at,
        )
