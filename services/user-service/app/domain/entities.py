from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """User domain entity without credentials."""

    id: int
    username: str
    email: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class UserWithCredentials:
    """User with password hash — only used in authentication flows.

    Separated from User to prevent credentials from leaking into
    read operations.
    """

    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class OutboxEntry:
    """Read-only snapshot of a pending outbox event.

    Used by the outbox publisher worker to know what to publish
    and how many retries have been attempted.
    """

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
