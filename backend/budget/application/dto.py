"""
Data Transfer Objects for budget use cases.
Re-exports shared Pydantic schemas as application DTO aliases.
"""
from backend.shared.schemas.budget import (
    BudgetCreate as BudgetCreateDTO,
    BudgetUpdate as BudgetUpdateDTO,
    BudgetInDB as BudgetResponseDTO,
)

__all__ = [
    "BudgetCreateDTO",
    "BudgetUpdateDTO",
    "BudgetResponseDTO",
]
