"""TAX-14 — a rule nobody can reach is not coverage.

The seed audit counted 82 rules and called it coverage, but 75 of them could
never fire from the import path: 33 because direction was inferred from a sign
transaction-service never sends, and 42 because no caller can supply a merchant
field. A count over the rule table cannot see that. These tests measure
reachability instead of existence, so the same gap fails the suite next time.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.adapters.outbound.rule_engine import ConstrainedRuleEngine, PersistedSeedRule
from app.domain.seed_contracts import MatchField, TransactionDirection
from app.domain.seed_rules import GLOBAL_RULES
from app.domain.value_objects import Confidence, Direction, direction_from_transaction_type

# What a producer of a categorize request can actually populate today. The
# import path knows the description and the transaction type; nothing upstream
# of transaction-service survives into a merchant or counterparty column.
PRODUCER_DIRECTIONS: set[Direction] = {"incoming", "outgoing"}
PRODUCER_MATCH_FIELDS = {MatchField.DESCRIPTION}

# Known gap owned by TAX-12, locked to its measured size so it cannot grow
# unnoticed and so landing TAX-12 forces this number down.
MERCHANT_ONLY_RULES = 42


class TestDirectionReachability:
    def test_every_rule_direction_is_one_a_producer_can_send(self) -> None:
        producible = {TransactionDirection(value) for value in PRODUCER_DIRECTIONS}
        unreachable = [rule.rule_key for rule in GLOBAL_RULES if rule.direction not in producible]
        assert unreachable == [], f"no producer can send the direction these rules require: {unreachable}"

    def test_both_directions_are_actually_exercised_by_the_seed_set(self) -> None:
        directions = {rule.direction for rule in GLOBAL_RULES}
        assert directions == {TransactionDirection.INCOMING, TransactionDirection.OUTGOING}

    def test_transaction_type_maps_onto_the_directions_rules_use(self) -> None:
        assert direction_from_transaction_type("expense") == "outgoing"
        assert direction_from_transaction_type("income") == "incoming"

    @pytest.mark.parametrize("bad", ["", None, "transfer", "unknown"])
    def test_an_underivable_direction_raises_instead_of_defaulting(self, bad: str | None) -> None:
        # A default here would silently match the wrong half of the rule set,
        # which is exactly how the original defect stayed invisible.
        with pytest.raises(ValueError, match="cannot derive categorization direction"):
            direction_from_transaction_type(bad)


class TestMatchFieldReachability:
    def test_merchant_only_rules_stay_at_their_measured_count(self) -> None:
        unreachable = [rule.rule_key for rule in GLOBAL_RULES if rule.match_field not in PRODUCER_MATCH_FIELDS]
        assert len(unreachable) == MERCHANT_ONLY_RULES, (
            f"{len(unreachable)} rules need evidence no producer sends, expected {MERCHANT_ONLY_RULES}. "
            "If TAX-12 landed, lower MERCHANT_ONLY_RULES; if it grew, a new rule is dead on arrival."
        )

    def test_the_reachable_remainder_is_not_empty(self) -> None:
        reachable = [rule.rule_key for rule in GLOBAL_RULES if rule.match_field in PRODUCER_MATCH_FIELDS]
        assert len(reachable) == len(GLOBAL_RULES) - MERCHANT_ONLY_RULES


class TestRealBankDescriptions:
    """The seven descriptions from the finding, at the direction they arrive with."""

    @pytest.fixture
    def engine(self) -> ConstrainedRuleEngine:
        return ConstrainedRuleEngine(
            [
                PersistedSeedRule(
                    target_subcategory_id=174,
                    target_category_id=36,
                    match_field="description",
                    operator="contains",
                    direction="outgoing",
                    confidence=Confidence.MEDIUM,
                    pattern="mobilepay",
                ),
                PersistedSeedRule(
                    target_subcategory_id=109,
                    target_category_id=24,
                    match_field="merchant",
                    operator="equals",
                    direction="outgoing",
                    confidence=Confidence.HIGH,
                    pattern="netto",
                ),
                PersistedSeedRule(
                    target_subcategory_id=164,
                    target_category_id=35,
                    match_field="description",
                    operator="contains",
                    direction="incoming",
                    confidence=Confidence.MEDIUM,
                    pattern="boligstoette",
                    minimum_amount=Decimal("1"),
                ),
            ]
        )

    def test_outgoing_description_rule_matches_when_direction_is_sent(self, engine: ConstrainedRuleEngine) -> None:
        # The regression in one assertion: the stored amount is unsigned, so
        # only an explicit direction gets this row to its rule.
        result = engine.match("MobilePay Telenor 24836308437046", 299.00, direction="outgoing")
        assert result is not None
        assert (result.category_id, result.subcategory_id) == (36, 174)

    def test_the_same_row_read_as_incoming_finds_nothing(self, engine: ConstrainedRuleEngine) -> None:
        assert engine.match("MobilePay Telenor 24836308437046", 299.00, direction="incoming") is None

    def test_incoming_rule_still_matches_incoming_rows(self, engine: ConstrainedRuleEngine) -> None:
        result = engine.match("Boligstøtte", 820.00, direction="incoming")
        assert result is not None
        assert (result.category_id, result.subcategory_id) == (35, 164)

    def test_grocery_chains_stay_unmatched_until_tax12(self, engine: ConstrainedRuleEngine) -> None:
        # Documented split between the plans: direction alone does not reach a
        # merchant-field rule, because there is still no merchant to match.
        assert engine.match("NETTO 7760", 41.09, direction="outgoing") is None
        assert engine.match("NETTO 7760", 41.09, direction="outgoing", merchant="NETTO") is not None
