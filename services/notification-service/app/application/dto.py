from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities import Notification


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    is_read: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, n: Notification) -> "NotificationResponse":
        return cls(
            id=n.id,  # type: ignore[arg-type]  # persisted entities always have an id
            type=n.type.value,
            title=n.title,
            body=n.body,
            is_read=n.is_read,
            created_at=n.created_at,  # type: ignore[arg-type]
        )


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    updated: int
