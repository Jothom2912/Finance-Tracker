"""
Domain entities for Category bounded context.

Three-level hierarchy:
  Category (top) -> SubCategory -> Merchant (learned)

Design choices:
  - Category and SubCategory are primarily static (seeded at startup)
  - Merchant is a learned entity that builds up from transaction data
  - All entities use int IDs (behind repository ports for future UUID swap)
  - Value objects (CategorizationResult, MerchantMapping) live in value_objects.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .value_objects import CategoryType


@dataclass
class Category:
    """
    Top-level category: Mad & drikke, Bolig, Transport, etc.

    Static — seeded at startup, rarely changed.
    """

    id: Optional[int]
    name: str
    type: CategoryType
    display_order: int = 0

    def is_expense(self) -> bool:
        return self.type == CategoryType.EXPENSE

    def is_income(self) -> bool:
        return self.type == CategoryType.INCOME

    def is_transfer(self) -> bool:
        return self.type == CategoryType.TRANSFER


@dataclass
class SubCategory:
    """
    Second level: Dagligvarer, Restaurant, Offentlig transport, etc.

    Primarily static, but users can add custom subcategories.
    """

    id: Optional[int]
    name: str
    category_id: int
    is_default: bool = True

    @staticmethod
    def create(name: str, category_id: int, *, is_default: bool = True) -> SubCategory:
        return SubCategory(id=None, name=name, category_id=category_id, is_default=is_default)


@dataclass
class Merchant:
    """
    Third level: learned entity from transaction data.

    Builds up over time. When a transaction with description
    "Netto 2150 Nordhavn" matches, merchant "Netto" is
    created/updated with subcategory "Dagligvarer".

    normalized_name is used for matching (lowercase, trimmed).
    display_name is shown in the UI.
    """

    id: Optional[int]
    normalized_name: str
    display_name: str
    subcategory_id: int
    transaction_count: int = 0
    is_user_confirmed: bool = False

    @staticmethod
    def create(
        normalized_name: str,
        display_name: str,
        subcategory_id: int,
    ) -> Merchant:
        return Merchant(
            id=None,
            normalized_name=normalized_name,
            display_name=display_name,
            subcategory_id=subcategory_id,
        )

    def confirm(self) -> None:
        """User confirms that this merchant mapping is correct."""
        self.is_user_confirmed = True

    def increment_count(self) -> None:
        self.transaction_count += 1
