from __future__ import annotations

from decimal import Decimal

import pytest
from app.domain.seed_contracts import (
    AuditDisposition,
    CategorizationRuleSeed,
    LegacyRuleAudit,
    MatchField,
    MatchOperator,
    TransactionDirection,
    validate_legacy_audit,
)
from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS
from app.domain.value_objects import Confidence


def _audit(keyword: str = "netto", target: str = "groceries") -> LegacyRuleAudit:
    return LegacyRuleAudit(
        legacy_keyword=keyword,
        old_target="Dagligvarer",
        disposition=AuditDisposition.RETAIN,
        proposed_target_key=target,
        rationale="Merchant identity is sufficiently specific.",
    )


def test_legacy_input_snapshot_is_sorted_and_complete() -> None:
    snapshot = tuple(
        sorted(
            (keyword, mapping["subcategory"], mapping["display"]) for keyword, mapping in SEED_MERCHANT_MAPPINGS.items()
        )
    )

    assert len(snapshot) == 130
    assert len({keyword for keyword, _, _ in snapshot}) == 130
    assert snapshot[0] == ("10er bar", "Barer/natteliv", "10'er Bar")
    assert snapshot[-1] == ("zoo", "Oplevelser", "Zoo")


@pytest.mark.parametrize(
    ("entries", "legacy", "targets", "message"),
    [
        ([], {"netto"}, {"groceries"}, "missing legacy keywords"),
        ([_audit(), _audit()], {"netto"}, {"groceries"}, "duplicate legacy keywords"),
        ([_audit(target="unknown")], {"netto"}, {"groceries"}, "unknown target keys"),
    ],
)
def test_audit_validation_rejects_coverage_and_target_errors(
    entries: list[LegacyRuleAudit],
    legacy: set[str],
    targets: set[str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_legacy_audit(entries, legacy_keywords=legacy, target_keys=targets)


def test_replacement_requires_link_to_target_rule() -> None:
    row = LegacyRuleAudit(
        legacy_keyword="cafe",
        old_target="Kaffebar",
        disposition=AuditDisposition.REPLACE,
        proposed_target_key="restaurant_cafe",
        rationale="The broad fragment is unsafe.",
    )

    with pytest.raises(ValueError, match="replacement linkage required"):
        validate_legacy_audit([row], legacy_keywords={"cafe"}, target_keys={"restaurant_cafe"})


def test_rule_contract_requires_one_source_and_valid_inclusive_bounds() -> None:
    with pytest.raises(ValueError, match="exactly one merchant"):
        CategorizationRuleSeed(
            rule_key="netto",
            target_key="groceries",
            merchant_key="netto",
            pattern="netto",
            match_field=MatchField.MERCHANT,
            operator=MatchOperator.EQUALS,
            direction=TransactionDirection.OUTGOING,
            confidence=Confidence.HIGH,
            provenance="review:TAX-05",
            seed_version="2026-08-01",
        )

    with pytest.raises(ValueError, match="minimum_amount"):
        CategorizationRuleSeed(
            rule_key="netto",
            target_key="groceries",
            merchant_key="netto",
            match_field=MatchField.MERCHANT,
            operator=MatchOperator.EQUALS,
            direction=TransactionDirection.OUTGOING,
            confidence=Confidence.HIGH,
            provenance="review:TAX-05",
            seed_version="2026-08-01",
            minimum_amount=Decimal("100"),
            maximum_amount=Decimal("10"),
        )
