"""
Domain entities for Transaction bounded context.
Pure domain objects with no infrastructure dependencies.
"""

import enum
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


@dataclass
class Transaction:
    """Core transaction entity."""

    id: Optional[int]
    amount: float
    description: Optional[str]
    date: date
    type: str
    category_id: int
    account_id: int
    created_at: Optional[datetime] = None
    subcategory_id: Optional[int] = None
    merchant_id: Optional[int] = None
    categorization_tier: Optional[str] = None
    categorization_confidence: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("Account ID is required")
        if not self.category_id:
            raise ValueError("Category ID is required")

    @property
    def is_expense(self) -> bool:
        return self.type == "expense"

    @property
    def is_income(self) -> bool:
        return self.type == "income"


@dataclass
class PlannedTransaction:
    """Planned/recurring transaction entity."""

    id: Optional[int]
    name: Optional[str]
    amount: float
    transaction_id: Optional[int] = None


@dataclass
class CategoryInfo:
    """Minimal category info from Category domain (anti-corruption layer)."""

    id: int
    name: str
    type: str
