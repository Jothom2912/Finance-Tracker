"""
Value objects for Category bounded context.

Immutable objects defined by their attributes.
All frozen dataclasses and enums — no mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class CategoryType(Enum):
    """Top-level classification for aggregation and analytics."""

    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


class CategoryLevel(Enum):
    """Hierarchy level. PRODUCT reserved for future receipt OCR."""

    CATEGORY = 1
    SUBCATEGORY = 2
    MERCHANT = 3


class CategorizationTier(Enum):
    """Which pipeline step resolved the categorization."""

    RULE = "rule"
    ML = "ml"
    LLM = "llm"
    MANUAL = "manual"
    FALLBACK = "fallback"


class Confidence(Enum):
    """Discrete confidence level instead of arbitrary floats."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MappingSource(Enum):
    """Origin of a merchant mapping."""

    SEED = "seed"
    LEARNED = "learned"
    MANUAL = "manual"


# ──────────────────────────────────────────────
# Value objects (frozen dataclasses)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class CategorizationResult:
    """
    Immutable result of categorizing a single transaction.

    Stored on the transaction to track how and with what
    confidence it was categorized.

    Example:
        category_id    -> "Mad & drikke"
        subcategory_id -> "Dagligvarer"
        merchant_id    -> "Netto"
        tier           -> RULE
        confidence     -> HIGH
    """

    category_id: int
    subcategory_id: int
    merchant_id: Optional[int] = None
    tier: CategorizationTier = CategorizationTier.RULE
    confidence: Confidence = Confidence.HIGH

    @property
    def was_auto_categorized(self) -> bool:
        return self.tier != CategorizationTier.MANUAL

    @property
    def needs_review(self) -> bool:
        """Low confidence results should be surfaced for user review."""
        return self.confidence == Confidence.LOW


@dataclass(frozen=True)
class MerchantMapping:
    """
    Rule mapping a keyword to a merchant + subcategory.

    This is what the current category_rules dict becomes,
    but as a first-class domain value object instead of a dict.
    """

    keyword: str
    merchant_id: int
    subcategory_id: int
    source: MappingSource = MappingSource.SEED
