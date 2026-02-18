"""
Value objects for Category domain.
Immutable objects defined by their attributes.
"""
from enum import Enum


class CategoryType(Enum):
    """Category type - income or expense."""
    INCOME = "income"
    EXPENSE = "expense"
