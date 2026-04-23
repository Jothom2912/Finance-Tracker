"""Domain entities for the Categorization bounded context.

Hierarchy: Category -> SubCategory -> Merchant (learned)
Plus: CategorizationRule (data-driven rules) and CategorizationResultRecord (audit).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.domain.value_objects import CategorizationTier, CategoryType, Confidence, PatternType


@dataclass
class Category:
    id: Optional[int]
    name: str
    type: CategoryType
    display_order: int = 0


@dataclass
class SubCategory:
    id: Optional[int]
    name: str
    category_id: int
    is_default: bool = True

    @staticmethod
    def create(name: str, category_id: int, *, is_default: bool = True) -> SubCategory:
        return SubCategory(id=None, name=name, category_id=category_id, is_default=is_default)


@dataclass
class Merchant:
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


@dataclass
class CategorizationRule:
    """A data-driven categorization rule.

    user_id=None means system rule; otherwise user-specific.
    User rules typically get higher priority to override system defaults.
    """

    id: Optional[int]
    user_id: Optional[int]
    priority: int
    pattern_type: PatternType
    pattern_value: str
    matches_subcategory_id: int
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CategorizationResultRecord:
    """Append-only audit trail of categorization decisions."""

    id: Optional[int]
    transaction_id: int
    category_id: int
    subcategory_id: int
    merchant_id: Optional[int]
    tier: CategorizationTier
    confidence: Confidence
    model_version: str
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class OutboxEntry:
    """Read-only snapshot of a pending outbox event."""

    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: str
    correlation_id: str | None
    status: str
    attempts: int
    next_attempt_at: datetime
    created_at: datetime
