"""Value objects for the Categorization bounded context.

Immutable objects defined by their attributes.
All frozen dataclasses and enums — no mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional


class CategoryType(Enum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


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
    SEED = "seed"
    LEARNED = "learned"
    MANUAL = "manual"


class PatternType(Enum):
    """Rule pattern types supported by the categorization engine."""

    KEYWORD = "keyword"
    REGEX = "regex"
    MERCHANT = "merchant"
    AMOUNT_RANGE = "amount_range"


@dataclass(frozen=True)
class CategorizationResult:
    """Immutable result of categorizing a single transaction."""

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
        return self.confidence == Confidence.LOW


Direction = Literal["incoming", "outgoing"]

# transaction-service stores an unsigned amount and keeps the direction in
# ``transaction_type``, so this mapping — not the sign of the amount — is the
# only honest source of direction for rule constraints (TAX-14).
_DIRECTION_BY_TRANSACTION_TYPE: dict[str, Direction] = {
    "income": "incoming",
    "expense": "outgoing",
}


def direction_from_transaction_type(transaction_type: str | None) -> Direction:
    """Map a transaction type to a rule direction, or raise.

    Raising beats defaulting: a missing type makes the message retry and land
    in the DLQ, where it is visible, whereas a default would silently file the
    transaction under the wrong direction and match the wrong rules.
    """
    direction = _DIRECTION_BY_TRANSACTION_TYPE.get(str(transaction_type or "").lower())
    if direction is None:
        raise ValueError(f"cannot derive categorization direction from transaction_type {transaction_type!r}")
    return direction
