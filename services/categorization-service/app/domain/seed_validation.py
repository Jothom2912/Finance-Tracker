"""Cross-manifest validation for the inactive TAX-04 target seed."""

from __future__ import annotations

from collections import Counter

from app.domain.seed_contracts import (
    CategorizationRuleSeed,
    MatchField,
    MerchantSeed,
    TaxonomyDefinition,
)
from app.domain.value_objects import Confidence


def _duplicates(values: list[str]) -> set[str]:
    return {value for value, count in Counter(values).items() if count > 1}


def validate_target_manifests(
    taxonomy: tuple[TaxonomyDefinition, ...],
    merchants: tuple[MerchantSeed, ...],
    rules: tuple[CategorizationRuleSeed, ...],
) -> None:
    taxonomy_keys = {definition.semantic_key for definition in taxonomy}
    child_keys = {definition.semantic_key for definition in taxonomy if definition.parent_key is not None}
    merchant_keys = {merchant.merchant_key for merchant in merchants}
    aliases = [alias.normalized_value for merchant in merchants for alias in merchant.aliases]

    errors = []
    duplicate_taxonomy = _duplicates([definition.semantic_key for definition in taxonomy])
    duplicate_merchants = _duplicates([merchant.merchant_key for merchant in merchants])
    duplicate_aliases = _duplicates(aliases)
    duplicate_rules = _duplicates([rule.rule_key for rule in rules])
    orphan_parents = {
        definition.parent_key
        for definition in taxonomy
        if definition.parent_key is not None and definition.parent_key not in taxonomy_keys
    }
    orphan_targets = {rule.target_key for rule in rules} - child_keys
    orphan_merchants = {
        rule.merchant_key for rule in rules if rule.merchant_key is not None and rule.merchant_key not in merchant_keys
    }
    unsafe_confidence = {
        rule.rule_key
        for rule in rules
        if rule.match_field is MatchField.DESCRIPTION and rule.confidence is Confidence.HIGH
    }

    for label, values in (
        ("duplicate taxonomy keys", duplicate_taxonomy),
        ("duplicate merchant keys", duplicate_merchants),
        ("duplicate aliases", duplicate_aliases),
        ("duplicate rule keys", duplicate_rules),
        ("orphan parent keys", orphan_parents),
        ("orphan target keys", orphan_targets),
        ("orphan merchant keys", orphan_merchants),
        ("high-confidence description rules", unsafe_confidence),
    ):
        if values:
            errors.append(f"{label}: {sorted(values)}")
    if errors:
        raise ValueError("; ".join(errors))
