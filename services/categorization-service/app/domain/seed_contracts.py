"""Pure-domain contracts for the future global categorization seed.

These types describe the TAX-04 target.  They are intentionally not imported by the
runtime provider or migrations 001-007; TAX-06 owns persistence and activation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable

from app.domain.value_objects import CategoryType, Confidence


class AuditDisposition(str, Enum):
    RETAIN = "retain"
    CONSTRAIN = "constrain"
    REPLACE = "replace"
    PERSONA_ONLY = "persona_only"
    REMOVE = "remove"


class MatchField(str, Enum):
    MERCHANT = "merchant"
    COUNTERPARTY = "counterparty"
    DESCRIPTION = "description"


class MatchOperator(str, Enum):
    EQUALS = "equals"
    CONTAINS = "contains"
    PREFIX = "prefix"


class TransactionDirection(str, Enum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"
    ANY = "any"


class SeedLifecycle(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class TaxonomyDefinition:
    semantic_key: str
    display_name: str
    category_type: CategoryType
    description: str
    seed_version: str
    parent_key: str | None = None
    synonyms: tuple[str, ...] = ()
    is_fallback: bool = False
    lifecycle: SeedLifecycle = SeedLifecycle.ACTIVE


@dataclass(frozen=True, slots=True)
class MerchantAlias:
    normalized_value: str
    match_field: MatchField
    provider: str | None = None
    country: str | None = None


@dataclass(frozen=True, slots=True)
class MerchantSeed:
    merchant_key: str
    display_name: str
    aliases: tuple[MerchantAlias, ...]
    provenance: str
    seed_version: str
    lifecycle: SeedLifecycle = SeedLifecycle.ACTIVE


@dataclass(frozen=True, slots=True)
class CategorizationRuleSeed:
    rule_key: str
    target_key: str
    match_field: MatchField
    operator: MatchOperator
    direction: TransactionDirection
    confidence: Confidence
    provenance: str
    seed_version: str
    merchant_key: str | None = None
    pattern: str | None = None
    provider: str | None = None
    country: str | None = None
    minimum_amount: Decimal | None = None
    maximum_amount: Decimal | None = None
    lifecycle: SeedLifecycle = SeedLifecycle.ACTIVE

    def __post_init__(self) -> None:
        sources = (self.merchant_key is not None, self.pattern is not None)
        if sum(sources) != 1:
            raise ValueError("a rule must reference exactly one merchant or explicit pattern")
        if self.pattern is not None and self.pattern != self.pattern.strip().lower():
            raise ValueError("rule patterns must be normalized lowercase text")
        if self.minimum_amount is not None and self.maximum_amount is not None:
            if self.minimum_amount > self.maximum_amount:
                raise ValueError("minimum_amount must not exceed maximum_amount")
        if not self.provenance.strip():
            raise ValueError("rule provenance is required")


@dataclass(frozen=True, slots=True)
class LegacyRuleAudit:
    legacy_keyword: str
    old_target: str
    disposition: AuditDisposition
    proposed_target_key: str
    rationale: str
    replacement_rule_key: str | None = None


def validate_legacy_audit(
    entries: Iterable[LegacyRuleAudit],
    *,
    legacy_keywords: Iterable[str],
    target_keys: Iterable[str],
) -> None:
    """Reject incomplete, duplicate or semantically invalid TAX-05 audit rows."""
    audit_rows = tuple(entries)
    expected = set(legacy_keywords)
    targets = set(target_keys)
    counts = Counter(row.legacy_keyword for row in audit_rows)
    actual = set(counts)

    missing = expected - actual
    extra = actual - expected
    duplicates = {keyword for keyword, count in counts.items() if count != 1}
    unknown_targets = {row.proposed_target_key for row in audit_rows} - targets
    blank_rationales = {row.legacy_keyword for row in audit_rows if not row.rationale.strip()}
    missing_replacements = {
        row.legacy_keyword
        for row in audit_rows
        if row.disposition is AuditDisposition.REPLACE and row.replacement_rule_key is None
    }

    errors = []
    if missing:
        errors.append(f"missing legacy keywords: {sorted(missing)}")
    if extra:
        errors.append(f"unexpected legacy keywords: {sorted(extra)}")
    if duplicates:
        errors.append(f"duplicate legacy keywords: {sorted(duplicates)}")
    if unknown_targets:
        errors.append(f"unknown target keys: {sorted(unknown_targets)}")
    if blank_rationales:
        errors.append(f"blank rationales: {sorted(blank_rationales)}")
    if missing_replacements:
        errors.append(f"replacement linkage required: {sorted(missing_replacements)}")
    if errors:
        raise ValueError("; ".join(errors))
