"""
Domain entities for Goal bounded context.
Pure domain objects with no infrastructure dependencies.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Goal:
    """Goal domain entity representing a financial savings target."""
    id: Optional[int]
    name: Optional[str]
    target_amount: float
    current_amount: float
    target_date: Optional[date]
    status: Optional[str]
    account_id: int

    def __post_init__(self) -> None:
        if self.target_amount < 0:
            raise ValueError("Target amount must be >= 0")
        if self.current_amount < 0:
            raise ValueError("Current amount must be >= 0")
        if not self.account_id:
            raise ValueError("Account ID is required")

    @property
    def progress_percent(self) -> float:
        """Calculate progress towards goal as a percentage."""
        if self.target_amount == 0:
            return 100.0
        return round((self.current_amount / self.target_amount) * 100, 2)

    @property
    def is_completed(self) -> bool:
        """Check if goal has been reached."""
        return self.current_amount >= self.target_amount
