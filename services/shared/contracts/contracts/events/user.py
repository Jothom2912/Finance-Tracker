from __future__ import annotations

from contracts.base import BaseEvent


class UserCreatedEvent(BaseEvent):
    """Published when a new user account is registered."""

    event_type: str = "user.created"
    event_version: int = 1

    user_id: int
    email: str
    username: str
