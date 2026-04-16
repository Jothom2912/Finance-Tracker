from __future__ import annotations

from datetime import date

from contracts.base import BaseEvent


class TransactionCreatedEvent(BaseEvent):
    """Published when a financial transaction is recorded.

    ``amount`` is serialised as a string to preserve decimal precision.
    Consumers should parse it with ``Decimal(amount)``.

    The payload is denormalised: both ``category_id`` and ``category``
    (name) are included so downstream projections don't need lookups.
    ``tx_date`` is the date of the transaction (not event emission).
    """

    event_type: str = "transaction.created"
    event_version: int = 1

    transaction_id: int
    account_id: int
    user_id: int
    amount: str
    transaction_type: str
    tx_date: date
    category_id: int | None = None
    category: str = ""
    description: str = ""
    account_name: str = ""
    subcategory_id: int | None = None
    categorization_tier: str | None = None
    categorization_confidence: str | None = None


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
    transaction_type: str
    tx_date: date
    category_id: int | None = None
    category: str = ""
    previous_category: str = ""
    description: str = ""
    account_name: str = ""
    subcategory_id: int | None = None
    categorization_tier: str | None = None
    categorization_confidence: str | None = None


class TransactionDeletedEvent(BaseEvent):
    """Published when a financial transaction is removed."""

    event_type: str = "transaction.deleted"
    event_version: int = 1

    transaction_id: int
    account_id: int
    user_id: int
    amount: str
