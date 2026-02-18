"""
Domain entities for Transaction bounded context.
Pure domain objects with no infrastructure dependencies.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class Transaction:
    """Core transaction entity."""

    id: Optional[int]
    amount: float
    description: Optional[str]
    date: date
    type: str  # "income" or "expense"
    category_id: int
    account_id: int
    created_at: Optional[datetime] = None

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
