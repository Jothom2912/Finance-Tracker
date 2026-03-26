"""
Rule engine adapter — Tier 1 deterministic keyword matching.

Satisfies IRuleEngine Protocol from ports/outbound.py.

Two core behaviors:
  1. Longest-match-first: keywords sorted by length descending,
     so "dsb 7-eleven" matches before "dsb" and "7-eleven".
  2. Sign-dependent overrides: some keywords (renter, mobilepay,
     opsparing) map to different subcategories depending on
     whether the transaction amount is positive or negative.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.category.domain.value_objects import (
    CategorizationResult,
    CategorizationTier,
    Confidence,
)

logger = logging.getLogger(__name__)

# keyword -> (subcategory_name_for_positive, subcategory_name_for_negative)
SIGN_OVERRIDES: dict[str, tuple[str, str]] = {
    "renter": ("Renteindtaegter", "Renteudgifter"),
    "rente": ("Renteindtaegter", "Renteudgifter"),
    "mobilepay": ("MobilePay ind", "MobilePay ud"),
    "opsparing": ("Opsparing (ind)", "Opsparing (ud)"),
}


class RuleEngine:
    """
    Tier 1: deterministic keyword matching.

    Constructed with two data structures:
      keyword_mappings: list of (keyword, subcategory_name)
      subcategory_lookup: dict[subcategory_name -> (subcategory_id, category_id)]

    Both are built from DB data at startup (via seed script + DI wiring).
    """

    def __init__(
        self,
        keyword_mappings: list[tuple[str, str]],
        subcategory_lookup: dict[str, tuple[int, int]],
    ):
        self._sorted_keywords = sorted(
            keyword_mappings, key=lambda kv: len(kv[0]), reverse=True
        )
        self._lookup = subcategory_lookup

    def match(
        self, description: str, amount: float
    ) -> Optional[CategorizationResult]:
        desc_lower = description.lower()

        for keyword, subcategory_name in self._sorted_keywords:
            if keyword not in desc_lower:
                continue

            final_name = self._apply_sign_override(
                keyword, subcategory_name, amount
            )
            ids = self._lookup.get(final_name)
            if ids is None:
                logger.warning(
                    "Keyword '%s' mapped to unknown subcategory '%s'",
                    keyword, final_name,
                )
                continue

            subcat_id, cat_id = ids
            return CategorizationResult(
                category_id=cat_id,
                subcategory_id=subcat_id,
                tier=CategorizationTier.RULE,
                confidence=Confidence.HIGH,
            )

        return None

    @staticmethod
    def _apply_sign_override(
        keyword: str, default_subcategory: str, amount: float
    ) -> str:
        override = SIGN_OVERRIDES.get(keyword)
        if override is None:
            return default_subcategory

        positive_name, negative_name = override
        return positive_name if amount > 0 else negative_name
