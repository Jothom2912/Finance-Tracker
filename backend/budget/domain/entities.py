"""
Domain entities for Budget bounded context.
Pure domain objects with no infrastructure dependencies.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Budget:
    """Budget domain entity."""
    id: Optional[int]
    amount: float
    budget_date: Optional[date]
    account_id: int
    category_id: int

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Budget amount cannot be negative")
        if not self.account_id:
            raise ValueError("Account ID is required")
        if not self.category_id:
            raise ValueError("Category ID is required")
