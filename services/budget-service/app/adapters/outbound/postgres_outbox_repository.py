from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from contracts.base import BaseEvent
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IOutboxRepository
from app.models import OutboxEventModel


@dataclass(frozen=True)
class OutboxEntry:
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


def _utcnow_naive() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)


class PostgresOutboxRepository(IOutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        event: BaseEvent,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None:
        model = OutboxEventModel(
            id=str(uuid4()),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event.event_type,
            payload_json=event.to_json(),
            correlation_id=event.correlation_id,
            status="pending",
            attempts=0,
        )
        self._session.add(model)
        await self._session.flush()

    async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]:
        now = _utcnow_naive()
        stmt = (
            select(OutboxEventModel)
            .where(
                OutboxEventModel.status.in_(["pending", "failed"]),
                OutboxEventModel.next_attempt_at <= now,
            )
            .order_by(OutboxEventModel.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return [self._to_entry(m) for m in result.scalars().all()]

    async def mark_published(self, event_id: str) -> None:
        await self._session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(status="published", published_at=_utcnow_naive()),
        )

    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None:
        await self._session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(
                status="failed",
                attempts=OutboxEventModel.attempts + 1,
                next_attempt_at=next_attempt_at,
            ),
        )

    @staticmethod
    def _to_entry(model: OutboxEventModel) -> OutboxEntry:
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
