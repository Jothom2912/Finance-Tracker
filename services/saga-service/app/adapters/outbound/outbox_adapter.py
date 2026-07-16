from __future__ import annotations

from dataclasses import dataclass

from messaging import OutboxRepository
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IOutboxRepository
from app.models import OutboxEventModel


@dataclass(frozen=True)
class _CommandEnvelope:
    """Structural ``SerializableEvent`` for saga command payloads.

    Saga commands are dynamic dicts (built per step by the saga
    definition), not typed contract events — the envelope carries the
    already-serialized payload so the shared outbox can store it.
    """

    event_type: str
    correlation_id: str | None
    payload_json: str

    def to_json(self) -> str:
        return self.payload_json


class SagaOutboxAdapter(IOutboxRepository):
    """Adapts the shared ``messaging.OutboxRepository`` to the saga
    port's dict-based ``add`` signature.

    The port keeps ``(event_type, payload_json, ...)`` because saga
    commands have no typed event classes; wiring the shared repository
    in directly (as wave-B briefly did) violates the port and crashes
    the orchestrator at runtime — its call sites pass keywords the
    shared ``add(event, ...)`` does not accept.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._inner = OutboxRepository(session, OutboxEventModel)

    async def add(
        self,
        event_type: str,
        payload_json: str,
        aggregate_type: str,
        aggregate_id: str,
        correlation_id: str | None = None,
    ) -> None:
        await self._inner.add(
            _CommandEnvelope(event_type, correlation_id, payload_json),
            aggregate_type,
            aggregate_id,
        )
