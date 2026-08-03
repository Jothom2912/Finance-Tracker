"""Unit tests for the RuleEngine adapter (tier 1 keyword matching)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.adapters.outbound.rule_engine import ConstrainedRuleEngine, PersistedSeedRule, RuleEngine, TieredRuleEngine
from app.domain.value_objects import CategorizationTier, Confidence


@pytest.fixture()
def subcategory_lookup() -> dict[str, tuple[int, int]]:
    return {
        "Dagligvarer": (1, 1),
        "Restaurant": (2, 1),
        "Kiosk": (3, 1),
        "Offentlig transport": (4, 3),
        "Renteindtaegter": (5, 9),
        "Renteudgifter": (6, 7),
        "MobilePay ind": (7, 10),
        "MobilePay ud": (8, 10),
        "Opsparing (ind)": (9, 9),
        "Opsparing (ud)": (10, 10),
        "Anden": (99, 8),
    }


@pytest.fixture()
def keyword_mappings() -> list[tuple[str, str]]:
    return [
        ("netto", "Dagligvarer"),
        ("restaurant", "Restaurant"),
        ("dsb 7-eleven", "Kiosk"),
        ("7-eleven", "Kiosk"),
        ("dsb", "Offentlig transport"),
        ("renter", "Renteindtaegter"),
        ("rente", "Renteindtaegter"),
        ("mobilepay", "MobilePay ud"),
        ("opsparing", "Opsparing (ud)"),
    ]


@pytest.fixture()
def engine(
    keyword_mappings: list[tuple[str, str]],
    subcategory_lookup: dict[str, tuple[int, int]],
) -> RuleEngine:
    return RuleEngine(keyword_mappings, subcategory_lookup)


class TestBasicMatching:
    def test_exact_keyword_match(self, engine: RuleEngine) -> None:
        result = engine.match("Netto Nordhavn", -150.0, direction="outgoing")
        assert result is not None
        assert result.subcategory_id == 1
        assert result.category_id == 1
        assert result.tier == CategorizationTier.RULE
        assert result.confidence == Confidence.HIGH

    def test_no_match_returns_none(self, engine: RuleEngine) -> None:
        result = engine.match("Unknown merchant XYZ", -50.0, direction="outgoing")
        assert result is None

    def test_case_insensitive(self, engine: RuleEngine) -> None:
        result = engine.match("NETTO CITY", -100.0, direction="outgoing")
        assert result is not None
        assert result.subcategory_id == 1


class TestLongestMatchFirst:
    def test_dsb_7eleven_beats_dsb(self, engine: RuleEngine) -> None:
        result = engine.match("DSB 7-Eleven Koebenhavn H", -45.0, direction="outgoing")
        assert result is not None
        assert result.subcategory_id == 3  # Kiosk, not Offentlig transport

    def test_plain_dsb_matches_transport(self, engine: RuleEngine) -> None:
        result = engine.match("DSB Billet", -89.0, direction="outgoing")
        assert result is not None
        assert result.subcategory_id == 4  # Offentlig transport


class TestLegacyRulesHaveNoHiddenDirectionOverride:
    def test_amount_sign_does_not_retarget_a_user_keyword(self, engine: RuleEngine) -> None:
        positive = engine.match("Renter tilskrevet", 12.50, direction="incoming")
        negative = engine.match("Renter beregnet", -8.25, direction="outgoing")
        assert positive is not None and negative is not None
        assert positive.subcategory_id == negative.subcategory_id == 5


class TestDanishNormalization:
    def test_oe_normalization(self, engine: RuleEngine) -> None:
        result = engine.match("Køb hos Netto", -75.0, direction="outgoing")
        assert result is not None
        assert result.subcategory_id == 1


class TestTieredRuleEngine:
    """F1-02: tier order beats keyword length ACROSS tiers; longest-match
    still applies WITHIN a tier; falls through on no match."""

    def test_user_tier_beats_longer_global_keyword(
        self,
        subcategory_lookup: dict[str, tuple[int, int]],
    ) -> None:
        # Global has the LONGER keyword — flat longest-match would pick it.
        user_tier = RuleEngine([("netto", "Restaurant")], subcategory_lookup)
        global_tier = RuleEngine([("netto vesterbro", "Dagligvarer")], subcategory_lookup)
        tiered = TieredRuleEngine([user_tier, global_tier])

        result = tiered.match("Netto Vesterbro", -100.0, direction="outgoing")

        assert result is not None
        assert result.subcategory_id == 2  # Restaurant — user tier won

    def test_falls_through_to_global_when_user_tier_misses(
        self,
        subcategory_lookup: dict[str, tuple[int, int]],
    ) -> None:
        user_tier = RuleEngine([("fitness", "Kiosk")], subcategory_lookup)
        global_tier = RuleEngine([("netto", "Dagligvarer")], subcategory_lookup)
        tiered = TieredRuleEngine([user_tier, global_tier])

        result = tiered.match("Netto Vesterbro", -100.0, direction="outgoing")

        assert result is not None
        assert result.subcategory_id == 1  # Dagligvarer — global fallthrough

    def test_longest_match_preserved_within_a_tier(
        self,
        subcategory_lookup: dict[str, tuple[int, int]],
    ) -> None:
        user_tier = RuleEngine(
            [("dsb", "Offentlig transport"), ("dsb 7-eleven", "Kiosk")],
            subcategory_lookup,
        )
        tiered = TieredRuleEngine([user_tier])

        result = tiered.match("DSB 7-Eleven Hovedbanen", -45.0, direction="outgoing")

        assert result is not None
        assert result.subcategory_id == 3  # Kiosk — longest match in tier

    def test_no_match_anywhere_returns_none(
        self,
        subcategory_lookup: dict[str, tuple[int, int]],
    ) -> None:
        tiered = TieredRuleEngine([RuleEngine([("netto", "Dagligvarer")], subcategory_lookup)])

        assert tiered.match("Ukendt butik", -10.0, direction="outgoing") is None

    def test_empty_engine_list_returns_none(self) -> None:
        assert TieredRuleEngine([]).match("Netto", -10.0, direction="outgoing") is None


class TestConstrainedRuleEngine:
    def test_requires_structured_merchant_evidence_and_direction(self) -> None:
        rule = PersistedSeedRule(
            target_subcategory_id=42,
            target_category_id=11,
            match_field="merchant",
            operator="equals",
            direction="outgoing",
            confidence=Confidence.HIGH,
            pattern="netto",
            aliases=("netto",),
            country="DK",
            merchant_id=501,
        )
        engine = ConstrainedRuleEngine([rule])

        assert engine.match("NETTO", -100, direction="outgoing", country="DK") is None
        assert engine.match("NETTO", 100, direction="incoming", merchant="netto", country="DK") is None
        result = engine.match("card purchase", -100, direction="outgoing", merchant="NETTO", country="DK")
        assert result is not None
        assert (result.category_id, result.subcategory_id, result.merchant_id) == (11, 42, 501)

    def test_description_rule_honours_inclusive_amount_bounds(self) -> None:
        rule = PersistedSeedRule(
            target_subcategory_id=43,
            target_category_id=11,
            match_field="description",
            operator="contains",
            direction="outgoing",
            confidence=Confidence.MEDIUM,
            pattern="pizzeria",
            minimum_amount=Decimal("50"),
            maximum_amount=Decimal("200"),
        )
        engine = ConstrainedRuleEngine([rule])

        assert engine.match("PIZZERIA", -49.99, direction="outgoing") is None
        assert engine.match("PIZZERIA", -50, direction="outgoing") is not None
        assert engine.match("PIZZERIA", -200, direction="outgoing") is not None
        assert engine.match("PIZZERIA", -200.01, direction="outgoing") is None
