"""Inactive TAX-04 constrained-rule manifest produced by the TAX-05 audit."""

from __future__ import annotations

import re

from app.domain.legacy_rule_audit import LEGACY_RULE_AUDIT
from app.domain.merchant_aliases import ALIAS_TO_MERCHANT
from app.domain.seed_contracts import (
    AuditDisposition,
    CategorizationRuleSeed,
    MatchField,
    MatchOperator,
    TransactionDirection,
)
from app.domain.taxonomy_definitions import SEED_VERSION
from app.domain.value_objects import Confidence

_INCOME_TARGETS = {"salary", "public_benefits", "capital_income", "other_income", "refund"}
_MEDIUM_MERCHANTS = {"normal", "power"}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _direction(keyword: str, target_key: str) -> TransactionDirection:
    if keyword in {"mobilepay ind", "vipps mobilepay", "overfoersel mobilepay", "fra opsparing"}:
        return TransactionDirection.INCOMING
    if target_key in _INCOME_TARGETS:
        return TransactionDirection.INCOMING
    return TransactionDirection.OUTGOING


def _legacy_rule(keyword: str, target_key: str) -> CategorizationRuleSeed:
    merchant_key = ALIAS_TO_MERCHANT.get(keyword)
    structured = merchant_key is not None
    confidence = Confidence.HIGH if structured and keyword not in _MEDIUM_MERCHANTS else Confidence.MEDIUM
    return CategorizationRuleSeed(
        rule_key=f"legacy_{_key(keyword)}",
        target_key=target_key,
        merchant_key=merchant_key,
        pattern=None if structured else keyword,
        match_field=MatchField.MERCHANT if structured else MatchField.DESCRIPTION,
        operator=MatchOperator.EQUALS if structured else MatchOperator.CONTAINS,
        direction=_direction(keyword, target_key),
        confidence=confidence,
        provenance=f"legacy-seed-reviewed:TAX-05:{keyword}",
        seed_version=SEED_VERSION,
    )


_ACTIVE_DISPOSITIONS = {AuditDisposition.RETAIN, AuditDisposition.CONSTRAIN}

_AUDITED_RULES = tuple(
    _legacy_rule(row.legacy_keyword, row.proposed_target_key)
    for row in LEGACY_RULE_AUDIT
    if row.disposition in _ACTIVE_DISPOSITIONS
)

_REPLACEMENT_RULES = (
    CategorizationRuleSeed(
        rule_key="merchant_mcdonalds_takeaway",
        target_key="takeaway",
        merchant_key="mcdonalds",
        pattern=None,
        match_field=MatchField.MERCHANT,
        operator=MatchOperator.EQUALS,
        direction=TransactionDirection.OUTGOING,
        confidence=Confidence.HIGH,
        provenance="replacement-review:TAX-05:mcd",
        seed_version=SEED_VERSION,
    ),
    CategorizationRuleSeed(
        rule_key="pattern_pizzeria_takeaway",
        target_key="takeaway",
        merchant_key=None,
        pattern="pizzeria",
        match_field=MatchField.DESCRIPTION,
        operator=MatchOperator.CONTAINS,
        direction=TransactionDirection.OUTGOING,
        confidence=Confidence.MEDIUM,
        provenance="replacement-review:TAX-05:pizzaria",
        seed_version=SEED_VERSION,
    ),
    CategorizationRuleSeed(
        rule_key="pattern_kiosk_food",
        target_key="kiosk",
        merchant_key=None,
        pattern="kiosk",
        match_field=MatchField.DESCRIPTION,
        operator=MatchOperator.CONTAINS,
        direction=TransactionDirection.OUTGOING,
        confidence=Confidence.MEDIUM,
        provenance="replacement-review:TAX-05:kiioskh",
        seed_version=SEED_VERSION,
    ),
)

GLOBAL_RULES: tuple[CategorizationRuleSeed, ...] = _AUDITED_RULES + _REPLACEMENT_RULES
