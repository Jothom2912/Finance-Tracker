from __future__ import annotations

from collections import Counter
from decimal import Decimal

from app.domain.legacy_rule_audit import LEGACY_RULE_AUDIT
from app.domain.merchant_aliases import ALIAS_TO_MERCHANT, MERCHANTS
from app.domain.seed_contracts import (
    AuditDisposition,
    CategorizationRuleSeed,
    MatchField,
    MatchOperator,
    TransactionDirection,
    validate_legacy_audit,
)
from app.domain.seed_matching import RuleEvidence, direction_from_amount, normalize_seed_text, rule_applies
from app.domain.seed_rules import GLOBAL_RULES
from app.domain.seed_validation import validate_target_manifests
from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS
from app.domain.taxonomy_definitions import SUBCATEGORY_KEYS, TAXONOMY_DEFINITIONS
from app.domain.value_objects import Confidence


def test_approved_taxonomy_has_13_parents_67_children_and_one_fallback_each() -> None:
    parents = [definition for definition in TAXONOMY_DEFINITIONS if definition.parent_key is None]
    children = [definition for definition in TAXONOMY_DEFINITIONS if definition.parent_key is not None]
    fallbacks = Counter(definition.parent_key for definition in children if definition.is_fallback)

    assert len(parents) == 13
    assert len(children) == 67
    assert fallbacks == {definition.semantic_key: 1 for definition in parents}


def test_every_legacy_mapping_has_one_valid_audit_disposition() -> None:
    validate_legacy_audit(
        LEGACY_RULE_AUDIT,
        legacy_keywords=SEED_MERCHANT_MAPPINGS,
        target_keys=SUBCATEGORY_KEYS,
    )

    assert Counter(row.disposition for row in LEGACY_RULE_AUDIT) == {
        AuditDisposition.RETAIN: 47,
        AuditDisposition.CONSTRAIN: 32,
        AuditDisposition.REPLACE: 3,
        AuditDisposition.PERSONA_ONLY: 24,
        AuditDisposition.REMOVE: 24,
    }


def test_target_manifests_are_separate_and_migration_ready() -> None:
    validate_target_manifests(TAXONOMY_DEFINITIONS, MERCHANTS, GLOBAL_RULES)

    assert len(MERCHANTS) == 36
    assert len(GLOBAL_RULES) == 82
    assert Counter(rule.confidence for rule in GLOBAL_RULES) == {
        Confidence.HIGH: 40,
        Confidence.MEDIUM: 42,
    }
    assert all(rule.provenance and rule.seed_version for rule in GLOBAL_RULES)
    assert all(rule.target_key in SUBCATEGORY_KEYS for rule in GLOBAL_RULES)


def test_aliases_identify_merchants_without_owning_category_targets() -> None:
    assert ALIAS_TO_MERCHANT["dsb"] == "dsb"
    assert ALIAS_TO_MERCHANT["dsb service & retail"] == "dsb"
    assert all(not hasattr(alias, "target_key") for merchant in MERCHANTS for alias in merchant.aliases)


def _rule(
    *,
    pattern: str | None = "foetex",
    merchant_key: str | None = None,
    match_field: MatchField = MatchField.DESCRIPTION,
    operator: MatchOperator = MatchOperator.CONTAINS,
    confidence: Confidence = Confidence.MEDIUM,
    provider: str | None = None,
    country: str | None = None,
    minimum_amount: Decimal | None = None,
    maximum_amount: Decimal | None = None,
) -> CategorizationRuleSeed:
    return CategorizationRuleSeed(
        rule_key="test_rule",
        target_key="groceries",
        pattern=pattern,
        merchant_key=merchant_key,
        match_field=match_field,
        operator=operator,
        direction=TransactionDirection.OUTGOING,
        confidence=confidence,
        provenance="test:TAX-05",
        seed_version="test-v1",
        provider=provider,
        country=country,
        minimum_amount=minimum_amount,
        maximum_amount=maximum_amount,
    )


def test_matching_normalizes_danish_and_keeps_fields_distinct() -> None:
    text_rule = _rule(pattern="foetex")
    merchant_rule = _rule(
        pattern=None,
        merchant_key="foetex",
        match_field=MatchField.MERCHANT,
        operator=MatchOperator.EQUALS,
        confidence=Confidence.HIGH,
    )
    evidence = RuleEvidence("Køb hos FØTEX", None, None, Decimal("-125"))

    assert normalize_seed_text("  FØTEX Åby  ") == "foetex aaby"
    assert rule_applies(text_rule, evidence)
    assert not rule_applies(merchant_rule, evidence)
    assert rule_applies(merchant_rule, RuleEvidence("unrelated", "foetex", None, Decimal("-125")))


def test_direction_zero_provider_country_and_inclusive_amount_edges() -> None:
    rule = _rule(
        provider="nordigen",
        country="DK",
        minimum_amount=Decimal("10"),
        maximum_amount=Decimal("100"),
    )

    assert direction_from_amount(Decimal("1")) is TransactionDirection.INCOMING
    assert direction_from_amount(Decimal("-1")) is TransactionDirection.OUTGOING
    assert direction_from_amount(Decimal("0")) is None
    assert rule_applies(rule, RuleEvidence("foetex", None, None, Decimal("-10"), "nordigen", "DK"))
    assert rule_applies(rule, RuleEvidence("foetex", None, None, Decimal("-100"), "nordigen", "DK"))
    assert not rule_applies(rule, RuleEvidence("foetex", None, None, Decimal("-9.99"), "nordigen", "DK"))
    assert not rule_applies(rule, RuleEvidence("foetex", None, None, Decimal("0"), "nordigen", "DK"))
    assert not rule_applies(rule, RuleEvidence("foetex", None, None, Decimal("-10"), "other", "DK"))
    assert not rule_applies(rule, RuleEvidence("foetex", None, None, Decimal("-10"), "nordigen", "SE"))


def test_removed_broad_and_personal_fragments_are_not_active_target_patterns() -> None:
    rejected = {
        row.legacy_keyword
        for row in LEGACY_RULE_AUDIT
        if row.disposition in {AuditDisposition.REMOVE, AuditDisposition.PERSONA_ONLY}
    }
    active_patterns = {rule.pattern for rule in GLOBAL_RULES if rule.pattern is not None}

    assert rejected.isdisjoint(active_patterns)
    assert {"bar", "cafe", "normal", "power", "su", "rente"}.isdisjoint(active_patterns)
