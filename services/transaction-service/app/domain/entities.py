from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    type: CategoryType


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
