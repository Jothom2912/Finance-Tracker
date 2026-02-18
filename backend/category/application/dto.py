"""
Data Transfer Objects for category use cases.
Re-exports shared Pydantic schemas as application DTO aliases.
"""
from backend.shared.schemas.category import (
    CategoryCreate as CategoryCreateDTO,
    Category as CategoryResponseDTO,
)

__all__ = [
    "CategoryCreateDTO",
    "CategoryResponseDTO",
]
