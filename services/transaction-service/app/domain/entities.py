from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    type: CategoryType


@dataclass(frozen=True)
class SubCategory:
    """Event-synced read copy of categorization-service's subcategory."""

    id: int
    name: str
    category_id: int
    is_default: bool = True


@dataclass(frozen=True)
class Transaction:
    id: int
    user_id: int
    account_id: int
    account_name: str
    category_id: int | None
    category_name: str | None
    amount: Decimal
    transaction_type: TransactionType
    description: str | None
    date: date
    created_at: datetime
    # Categorization pipeline metadata.  All optional because
    # transactions may arrive without being categorized (e.g. direct
    # manual entry without a category match) and historical rows
    # predate the pipeline.
    subcategory_id: int | None = None
    # Denormalized sub-level name.  ``category_name`` is always the parent name.
    subcategory_name: str | None = None
    categorization_tier: str | None = None
    categorization_confidence: str | None = None
    # Source-system identity (Enable Banking entry_reference) — None for
    # manual/CSV rows.  Currency is implicitly DKK until F3-03.
    external_id: str | None = None
    currency: str = "DKK"


@dataclass(frozen=True)
class PlannedTransaction:
    id: int
    user_id: int
    account_id: int
    account_name: str
    category_id: int | None
    category_name: str | None
    amount: Decimal
    transaction_type: TransactionType
    description: str | None
    recurrence: str
    next_execution: date
    is_active: bool
    created_at: datetime


@dataclass(frozen=True)
class OutboxEntry:
    """Read-only snapshot of a pending outbox event."""

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


# ``amount`` is stored as an unsigned magnitude, so the categorizer cannot
# derive direction from its sign; ``transaction_type`` is the only source and
# must be sent explicitly (TAX-14).
_DIRECTION_BY_TYPE: dict[str, Literal["incoming", "outgoing"]] = {
    TransactionType.INCOME.value: "incoming",
    TransactionType.EXPENSE.value: "outgoing",
}


def direction_of(transaction_type: TransactionType | str | None) -> Literal["incoming", "outgoing"]:
    """Map a transaction type to the categorizer's direction, or raise.

    Raising beats defaulting: an unknown type is a bug we want to see, while a
    default would quietly match the wrong half of the rule set.
    """
    raw = transaction_type.value if isinstance(transaction_type, TransactionType) else str(transaction_type or "")
    direction = _DIRECTION_BY_TYPE.get(raw.lower())
    if direction is None:
        raise ValueError(f"cannot derive categorization direction from transaction_type {transaction_type!r}")
    return direction
