from __future__ import annotations

from decimal import Decimal

from contracts.base import BaseEvent


class AccountCreatedEvent(BaseEvent):
    """Published when a financial account is created for a user."""

    event_type: str = "account.created"
    event_version: int = 1

    account_id: int
    user_id: int
    account_name: str
    saldo: str = "0.00"
    budget_start_day: int = 1


class AccountUpdatedEvent(BaseEvent):
    """Published when an account is updated. Carries full state for self-healing sync."""

    event_type: str = "account.updated"
    event_version: int = 1

    account_id: int
    user_id: int
    name: str
    saldo: str
    budget_start_day: int


class AccountCreationFailedEvent(BaseEvent):
    """Published when automatic account creation fails after user signup."""

    event_type: str = "account.creation_failed"
    event_version: int = 1

    user_id: int
    reason: str
