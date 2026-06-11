from __future__ import annotations

from uuid import uuid4

from contracts.base import BaseEvent
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IOutboxRepository
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
            correlation_id=event.correlation_id,
            status="pending",
            attempts=0,
        )
        self._session.add(model)
        await self._session.flush()
