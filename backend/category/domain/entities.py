"""
Domain entities for Category bounded context.
Pure domain objects with no infrastructure dependencies.
"""
from dataclasses import dataclass
from typing import Optional

from .value_objects import CategoryType


@dataclass
class Category:
    """Core category entity."""
    id: Optional[int]
    name: str
    type: CategoryType
    description: Optional[str] = None

    def is_expense(self) -> bool:
        """Check if this category is for expenses."""
        return self.type == CategoryType.EXPENSE

    def is_income(self) -> bool:
        """Check if this category is for income."""
        return self.type == CategoryType.INCOME
