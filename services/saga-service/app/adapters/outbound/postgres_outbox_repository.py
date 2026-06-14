from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IOutboxRepository
from app.models import OutboxEventModel

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)


class PostgresOutboxRepository(IOutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        event_type: str,
        payload_json: str,
        aggregate_type: str,
        aggregate_id: str,
        correlation_id: str | None = None,
    ) -> None:
        model = OutboxEventModel(
            id=str(uuid4()),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload_json=payload_json,
            correlation_id=correlation_id,
            status="pending",
            attempts=0,
        )
        self._session.add(model)
        await self._session.flush()

    async def fetch_pending(self, batch_size: int = 20) -> list[OutboxEventModel]:
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
        return list(result.scalars().all())

    async def mark_published(self, event_id: str) -> None:
        now = _utcnow_naive()
        await self._session.execute(
            update(OutboxEventModel).where(OutboxEventModel.id == event_id).values(status="published", published_at=now)
        )

    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None:
        await self._session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(
                status="failed",
                attempts=OutboxEventModel.attempts + 1,
                next_attempt_at=next_attempt_at,
            )
        )
