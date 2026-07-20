"""Domain entities for the notification feed.

Pure domain: no SQLAlchemy, no HTTP, no clock reads. ``read``/``dismissed``
are computed from the timestamp columns rather than stored as separate
booleans (CLAUDE.md: computed properties over duplicated stored state).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class NotificationType(str, enum.Enum):
    BANK_SYNC_COMPLETED = "bank_sync_completed"
    GOAL_REACHED = "goal_reached"
    BUDGET_MONTH_CLOSED = "budget_month_closed"


@dataclass(frozen=True)
class NotificationContent:
    """The user-facing text of a notification, produced by the message
    builders in :mod:`app.domain.messages`. Carries the type so text and
    classification stay co-located and testable."""

    type: NotificationType
    title: str
    body: str


@dataclass
class Notification:
    """A single feed entry for one user.

    ``source_key`` is the deterministic idempotency key (unique per logical
    event) — the same key never produces two rows.
    """

    user_id: int
    type: NotificationType
    title: str
    body: str
    source_key: str
    id: UUID | None = None
    created_at: datetime | None = None
    read_at: datetime | None = None
    dismissed_at: datetime | None = None

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @property
    def is_dismissed(self) -> bool:
        return self.dismissed_at is not None

    @classmethod
    def from_content(
        cls,
        *,
        user_id: int,
        content: NotificationContent,
        source_key: str,
    ) -> "Notification":
        return cls(
            user_id=user_id,
            type=content.type,
            title=content.title,
            body=content.body,
            source_key=source_key,
        )
