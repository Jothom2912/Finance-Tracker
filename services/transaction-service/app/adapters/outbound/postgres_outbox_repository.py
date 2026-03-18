from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contracts.base import BaseEvent
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IOutboxRepository
from app.domain.entities import OutboxEntry
from app.models import OutboxEventModel


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
            correlation_id=getattr(event, "correlation_id", None),
            status="pending",
            attempts=0,
        )
        self._session.add(model)
        await self._session.flush()

    async def add_batch(
        self,
        entries: list[tuple[BaseEvent, str, str]],
    ) -> None:
        """Insert multiple outbox rows in a single bulk operation."""
        models = [
            OutboxEventModel(
                id=str(uuid4()),
                aggregate_type=agg_type,
                aggregate_id=agg_id,
                event_type=event.event_type,
                payload_json=event.to_json(),
                correlation_id=getattr(event, "correlation_id", None),
                status="pending",
                attempts=0,
            )
            for event, agg_type, agg_id in entries
        ]
        self._session.add_all(models)
        await self._session.flush()

    async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(OutboxEventModel)
            .where(
                OutboxEventModel.status.in_(["pending", "failed"]),
                OutboxEventModel.next_attempt_at <= now,
            )
            .order_by(
                OutboxEventModel.created_at,
            )
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return [self._to_entry(m) for m in result.scalars().all()]

    async def mark_published(self, event_id: str) -> None:
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(
                status="published",
                published_at=datetime.now(timezone.utc),
            )
        )
        await self._session.execute(stmt)

    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None:
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(
                status="failed",
                attempts=OutboxEventModel.attempts + 1,
                next_attempt_at=next_attempt_at,
            )
        )
        await self._session.execute(stmt)

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
