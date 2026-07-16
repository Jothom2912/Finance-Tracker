from __future__ import annotations

from contracts.base import BaseEvent
from messaging import OutboxRepository
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IOutboxRepository
from app.models import OutboxEventModel


class TransactionOutboxAdapter(OutboxRepository, IOutboxRepository):
    """Port-conforming adapter over the shared outbox repository.

    The service port's ``add_batch`` takes ``(event, aggregate_type,
    aggregate_id)`` tuples — every bulk-imported transaction is its own
    aggregate — while the shared ``add_batch`` binds ONE aggregate to
    all events.  Wiring the shared repository in directly (as wave-B
    briefly did) made both bulk import paths crash with a TypeError at
    runtime while unit tests stayed green on mocked UoWs.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OutboxEventModel)

    async def add_batch(  # type: ignore[override]
        self,
        entries: list[tuple[BaseEvent, str, str]],
    ) -> None:
        await self.add_entries(entries)
