"""Rule engine adapter — Tier 1 deterministic keyword matching.

Three core behaviors:
  1. Longest-match-first: keywords sorted by length descending
  2. Sign-dependent overrides: some keywords map differently for +/-
  3. Danish-character normalisation: oe->oe, ae->ae, aa->aa
"""

from __future__ import annotations

import logging
from typing import Optional

from app.domain.value_objects import (
    CategorizationResult,
    CategorizationTier,
    Confidence,
)

logger = logging.getLogger(__name__)

SIGN_OVERRIDES: dict[str, tuple[str, str]] = {
    "renter": ("Renteindtaegter", "Renteudgifter"),
    "rente": ("Renteindtaegter", "Renteudgifter"),
    "mobilepay": ("MobilePay ind", "MobilePay ud"),
    "opsparing": ("Opsparing (ind)", "Opsparing (ud)"),
}


def _normalize_for_matching(text: str) -> str:
    """Lowercase + Danish ASCII transliteration (oe->oe, ae->ae, aa->aa)."""
    return text.lower().replace("ø", "oe").replace("æ", "ae").replace("å", "aa")


class RuleEngine:
    """Tier 1: deterministic keyword matching.

    Constructed with:
      keyword_mappings:    list of (keyword, subcategory_name)
      subcategory_lookup:  dict[subcategory_name -> (subcategory_id, category_id)]

    Keywords are normalised once at construction time.
    """

    def __init__(
        self,
        keyword_mappings: list[tuple[str, str]],
        subcategory_lookup: dict[str, tuple[int, int]],
    ):
        normalised = [
            (_normalize_for_matching(keyword), subcategory_name) for keyword, subcategory_name in keyword_mappings
        ]
        self._sorted_keywords = sorted(normalised, key=lambda kv: len(kv[0]), reverse=True)
        self._lookup = subcategory_lookup

    def match(self, description: str, amount: float) -> Optional[CategorizationResult]:
        desc_normalised = _normalize_for_matching(description)

        for keyword, subcategory_name in self._sorted_keywords:
            if keyword not in desc_normalised:
                continue

            final_name = self._apply_sign_override(keyword, subcategory_name, amount)
            ids = self._lookup.get(final_name)
            if ids is None:
                logger.warning(
                    "Keyword '%s' mapped to unknown subcategory '%s'",
                    keyword,
                    final_name,
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
    def _apply_sign_override(keyword: str, default_subcategory: str, amount: float) -> str:
        override = SIGN_OVERRIDES.get(keyword)
        if override is None:
            return default_subcategory
        positive_name, negative_name = override
        return positive_name if amount > 0 else negative_name
