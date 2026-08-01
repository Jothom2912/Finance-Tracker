"""Rule engine adapter — Tier 1 deterministic keyword matching.

Two core behaviors:
  1. Longest-match-first: keywords sorted by length descending
  2. Danish-character normalisation: oe->oe, ae->ae, aa->aa
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from app.domain.value_objects import (
    CategorizationResult,
    CategorizationTier,
    Confidence,
)

logger = logging.getLogger(__name__)


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

    def match(
        self,
        description: str,
        amount: float,
        *,
        merchant: str | None = None,
        counterparty: str | None = None,
        provider: str | None = None,
        country: str | None = None,
    ) -> Optional[CategorizationResult]:
        desc_normalised = _normalize_for_matching(description)

        for keyword, subcategory_name in self._sorted_keywords:
            if keyword not in desc_normalised:
                continue

            ids = self._lookup.get(subcategory_name)
            if ids is None:
                logger.warning(
                    "Keyword '%s' mapped to unknown subcategory '%s'",
                    keyword,
                    subcategory_name,
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


class TieredRuleEngine:
    """Priority-tiered composition of RuleEngines (F1-02).

    Tries each engine in order and returns the first match.  Longest-
    match applies WITHIN a tier (each RuleEngine's own sorting), while
    tier order decides ACROSS priorities — so a user's short keyword
    beats a longer seed keyword, which flat longest-match would not.
    Satisfies the same IRuleEngine protocol as RuleEngine.
    """

    def __init__(self, engines: list[Any]):
        self._engines = engines

    def match(
        self,
        description: str,
        amount: float,
        *,
        merchant: str | None = None,
        counterparty: str | None = None,
        provider: str | None = None,
        country: str | None = None,
    ) -> Optional[CategorizationResult]:
        for engine in self._engines:
            result = engine.match(
                description,
                amount,
                merchant=merchant,
                counterparty=counterparty,
                provider=provider,
                country=country,
            )
            if result is not None:
                return result
        return None


@dataclass(frozen=True, slots=True)
class PersistedSeedRule:
    target_subcategory_id: int
    target_category_id: int
    match_field: str
    operator: str
    direction: str
    confidence: Confidence
    pattern: str
    aliases: tuple[str, ...] = ()
    provider: str | None = None
    country: str | None = None
    minimum_amount: Decimal | None = None
    maximum_amount: Decimal | None = None
    merchant_id: int | None = None


class ConstrainedRuleEngine:
    """TAX-06 rule engine: every match applies the persisted evidence constraints."""

    def __init__(self, rules: list[PersistedSeedRule]):
        self._rules = sorted(
            rules, key=lambda rule: max((len(v) for v in rule.aliases), default=len(rule.pattern)), reverse=True
        )

    def match(
        self,
        description: str,
        amount: float,
        *,
        merchant: str | None = None,
        counterparty: str | None = None,
        provider: str | None = None,
        country: str | None = None,
    ) -> Optional[CategorizationResult]:
        evidence = {
            "description": description,
            "merchant": merchant,
            "counterparty": counterparty,
        }
        direction = "incoming" if amount > 0 else "outgoing" if amount < 0 else "any"
        absolute_amount = Decimal(str(abs(amount)))
        for rule in self._rules:
            raw = evidence.get(rule.match_field)
            if raw is None or (rule.direction != "any" and rule.direction != direction):
                continue
            if rule.provider is not None and rule.provider != provider:
                continue
            if rule.country is not None and rule.country != country:
                continue
            if rule.minimum_amount is not None and absolute_amount < rule.minimum_amount:
                continue
            if rule.maximum_amount is not None and absolute_amount > rule.maximum_amount:
                continue
            normalized = _normalize_for_matching(raw)
            candidates = rule.aliases or (rule.pattern,)
            if not any(
                self._matches(normalized, _normalize_for_matching(value), rule.operator) for value in candidates
            ):
                continue
            return CategorizationResult(
                category_id=rule.target_category_id,
                subcategory_id=rule.target_subcategory_id,
                merchant_id=rule.merchant_id,
                tier=CategorizationTier.RULE,
                confidence=rule.confidence,
            )
        return None

    @staticmethod
    def _matches(value: str, pattern: str, operator: str) -> bool:
        if operator == "equals":
            return value == pattern
        if operator == "prefix":
            return value.startswith(pattern)
        return pattern in value
