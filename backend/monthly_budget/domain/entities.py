"""
Domain entities for MonthlyBudget bounded context.
Pure domain objects with no infrastructure dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BudgetLine:
    """A single category budget line within a monthly budget."""

    id: Optional[int]
    category_id: int
    amount: float

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Budget line amount cannot be negative")
        if not self.category_id:
            raise ValueError("Category ID is required for a budget line")


@dataclass
class MonthlyBudget:
    """
    Aggregate root: a complete budget for one account in one month.

    Contains zero or more BudgetLines, each targeting a single category.
    """

    id: Optional[int]
    month: int
    year: int
    account_id: int
    lines: list[BudgetLine] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"Month must be 1-12, got {self.month}")
        if not 2000 <= self.year <= 9999:
            raise ValueError(f"Year must be 2000-9999, got {self.year}")
        if not self.account_id:
            raise ValueError("Account ID is required")

    @property
    def total_budget(self) -> float:
        return sum(line.amount for line in self.lines)
