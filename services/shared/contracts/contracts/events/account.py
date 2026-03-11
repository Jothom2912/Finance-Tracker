from __future__ import annotations

from contracts.base import BaseEvent


class AccountCreatedEvent(BaseEvent):
    """Published when a financial account is created for a user."""

    event_type: str = "account.created"
    event_version: int = 1

    account_id: int
    user_id: int
    account_name: str


class AccountCreationFailedEvent(BaseEvent):
    """Published when automatic account creation fails after user signup."""

    event_type: str = "account.creation_failed"
    event_version: int = 1

    user_id: int
    reason: str
