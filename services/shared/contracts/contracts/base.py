from __future__ import annotations

from datetime import datetime, timezone
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class BaseEvent(BaseModel):
    """Immutable base class for all inter-service domain events.

    Subclasses define typed payload fields directly rather than using a
    generic ``payload: dict``.  Every event carries routing metadata
    (``event_type``, ``event_version``) and tracing metadata
    (``correlation_id``, ``timestamp``).
    """

    model_config = ConfigDict(frozen=True)

    event_type: str
    event_version: int = 1
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> Self:
        return cls.model_validate_json(data)
