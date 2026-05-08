"""Sync outbox repository — operates on the same Session as account repos.

Inserts are flushed (not committed) so the caller controls the
transaction boundary via Unit of Work commit().
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.entities import OutboxEntry
from app.models.outbox import OutboxEventModel


class SyncOutboxRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        event_type: str,
        payload: dict,
        aggregate_type: str,
        aggregate_id: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        model = OutboxEventModel(
            id=str(uuid4()),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload_json=json.dumps(payload),
            correlation_id=correlation_id,
            status="pending",
            attempts=0,
        )
        self._session.add(model)
        self._session.flush()

    def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]:
        """Used by the async publisher — but defined here for completeness."""
        raise NotImplementedError("Use the async publisher worker for fetching")

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
