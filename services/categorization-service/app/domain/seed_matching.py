"""Reference semantics for constrained target rules; not wired into runtime."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.seed_contracts import (
    CategorizationRuleSeed,
    MatchField,
    MatchOperator,
    TransactionDirection,
)


def normalize_seed_text(value: str) -> str:
    return " ".join(value.lower().replace("ø", "oe").replace("æ", "ae").replace("å", "aa").split())


def direction_from_amount(amount: Decimal) -> TransactionDirection | None:
    if amount > 0:
        return TransactionDirection.INCOMING
    if amount < 0:
        return TransactionDirection.OUTGOING
    return None


@dataclass(frozen=True, slots=True)
class RuleEvidence:
    description: str
    merchant_key: str | None
    counterparty: str | None
    amount: Decimal
    provider: str | None = None
    country: str | None = None


def rule_applies(rule: CategorizationRuleSeed, evidence: RuleEvidence) -> bool:
    direction = direction_from_amount(evidence.amount)
    if direction is None and rule.direction is not TransactionDirection.ANY:
        return False
    if direction is not None and rule.direction not in {TransactionDirection.ANY, direction}:
        return False
    if rule.provider is not None and rule.provider != evidence.provider:
        return False
    if rule.country is not None and rule.country != evidence.country:
        return False

    absolute_amount = abs(evidence.amount)
    if rule.minimum_amount is not None and absolute_amount < rule.minimum_amount:
        return False
    if rule.maximum_amount is not None and absolute_amount > rule.maximum_amount:
        return False

    if rule.merchant_key is not None:
        return rule.merchant_key == evidence.merchant_key

    if rule.match_field is MatchField.DESCRIPTION:
        candidate = normalize_seed_text(evidence.description)
    elif rule.match_field is MatchField.COUNTERPARTY:
        candidate = normalize_seed_text(evidence.counterparty or "")
    else:
        return False

    pattern = rule.pattern or ""
    if rule.operator is MatchOperator.EQUALS:
        return candidate == pattern
    if rule.operator is MatchOperator.PREFIX:
        return candidate.startswith(pattern)
    return pattern in candidate
