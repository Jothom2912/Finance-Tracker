from __future__ import annotations

from contracts.base import BaseEvent


class TransactionCreatedEvent(BaseEvent):
    """Published when a financial transaction is recorded.

    ``amount`` is serialised as a string to preserve decimal precision.
    Consumers should parse it with ``Decimal(amount)``.
    """

    event_type: str = "transaction.created"
    event_version: int = 1

    transaction_id: int
    account_id: int
    user_id: int
    amount: str
    category: str
    description: str


class TransactionUpdatedEvent(BaseEvent):
    """Published when a financial transaction is modified.

    Carries both current and previous values for ``amount`` and
    ``category`` so downstream consumers (e.g. budget-service) can
    compute deltas without fetching the old state.
    """

    event_type: str = "transaction.updated"
    event_version: int = 1

    transaction_id: int
    account_id: int
    user_id: int
    amount: str
    previous_amount: str
    category: str
    previous_category: str
    description: str


class TransactionDeletedEvent(BaseEvent):
    """Published when a financial transaction is removed."""

    event_type: str = "transaction.deleted"
    event_version: int = 1

    transaction_id: int
    account_id: int
    user_id: int
    amount: str
