from __future__ import annotations

from collections.abc import Sequence

from contracts.base import BaseEvent
from messaging import OutboxRepository
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IOutboxRepository
from app.models import OutboxEventModel


# P2-32, in its multiple-inheritance shape: both bases declare fetch_pending, and
# they return two different classes both named OutboxEntry — the shared one and this
# service's domain copy. Fields are identical so duck-typing carries it; the fix is a
# mapping in the adapter, which is a runtime change spanning 7 services.
# warn_unused_ignores makes this line fail the day it lands.
# See dev-notes/findings/2026-07-27-outbox-port-declares-foreign-entity.md
class TransactionOutboxAdapter(OutboxRepository, IOutboxRepository):  # type: ignore[misc]
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
        entries: Sequence[tuple[BaseEvent, str, str]],
    ) -> None:
        await self.add_entries(entries)
