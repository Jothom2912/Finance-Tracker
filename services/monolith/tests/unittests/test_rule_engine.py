"""
Unit tests for RuleEngine — Tier 1 keyword matching.

Tests:
  - Longest-match-first behavior
  - Sign-dependent keyword overrides (renter, mobilepay, opsparing)
  - Case insensitivity
  - No match returns None
  - Missing subcategory in lookup is skipped
"""

import pytest

from backend.category.adapters.outbound.rule_engine import RuleEngine
from backend.category.domain.value_objects import (
    CategorizationTier,
    Confidence,
)

# Subcategory lookup: name -> (subcategory_id, category_id)
LOOKUP = {
    "Dagligvarer": (10, 1),
    "Restaurant": (11, 1),
    "Kaffebar": (12, 1),
    "Kiosk": (13, 1),
    "Offentlig transport": (30, 3),
    "Renteindtaegter": (91, 9),
    "Renteudgifter": (71, 7),
    "MobilePay ind": (101, 10),
    "MobilePay ud": (102, 10),
    "Opsparing (ind)": (93, 9),
    "Opsparing (ud)": (104, 10),
    "Fitness/sport": (41, 4),
    "Barer/natteliv": (42, 4),
    "Abonnementer": (43, 4),
    "Gebyrer": (72, 7),
    "Anden": (80, 8),
}

# Keyword mappings matching a subset of SEED_MERCHANT_MAPPINGS
KEYWORDS: list[tuple[str, str]] = [
    ("netto", "Dagligvarer"),
    ("restaurant", "Restaurant"),
    ("kosem restaurant", "Restaurant"),
    ("cafe", "Kaffebar"),
    ("cafe grotten", "Restaurant"),
    ("den franske cafe", "Restaurant"),
    ("7-eleven", "Kiosk"),
    ("dsb 7-eleven", "Kiosk"),
    ("dsb", "Offentlig transport"),
    ("dsb service & retail", "Offentlig transport"),
    ("dsb ungdomskort", "Offentlig transport"),
    ("renter", "Renteindtaegter"),
    ("rente", "Renteindtaegter"),
    ("mobilepay", "MobilePay ud"),
    ("mobilepay ind", "MobilePay ind"),
    ("mobilepay ud", "MobilePay ud"),
    ("opsparing", "Opsparing (ud)"),
    ("fra opsparing", "Opsparing (ind)"),
    ("fitness dk", "Fitness/sport"),
    ("fitness", "Fitness/sport"),
    ("bar", "Barer/natteliv"),
    ("escobar", "Barer/natteliv"),
    ("spotify", "Abonnementer"),
    ("gebyr", "Gebyrer"),
]


@pytest.fixture
def engine() -> RuleEngine:
    return RuleEngine(keyword_mappings=KEYWORDS, subcategory_lookup=LOOKUP)


# ──────────────────────────────────────────────
# Longest-match-first
# ──────────────────────────────────────────────


class TestLongestMatchFirst:
    def test_dsb_7eleven_matches_kiosk_not_dsb(self, engine: RuleEngine) -> None:
        """'dsb 7-eleven' (13 chars) beats 'dsb' (3 chars) and '7-eleven' (8 chars)."""
        result = engine.match("DSB 7-Eleven Koebenhavn", amount=-42.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Kiosk"][0]

    def test_dsb_alone_matches_transport(self, engine: RuleEngine) -> None:
        result = engine.match("DSB Billet app", amount=-89.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Offentlig transport"][0]

    def test_dsb_service_retail_matches_transport(self, engine: RuleEngine) -> None:
        """'dsb service & retail' (20 chars) is longer than 'dsb' (3 chars)."""
        result = engine.match("DSB SERVICE & RETAIL Noerreport", amount=-35.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Offentlig transport"][0]

    def test_cafe_grotten_matches_restaurant_not_kaffebar(self, engine: RuleEngine) -> None:
        """'cafe grotten' (12 chars) beats 'cafe' (4 chars)."""
        result = engine.match("CAFE GROTTEN 2100 Koebenhavn", amount=-150.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Restaurant"][0]

    def test_bare_cafe_matches_kaffebar(self, engine: RuleEngine) -> None:
        result = engine.match("Cafe Nero", amount=-45.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Kaffebar"][0]

    def test_fitness_dk_matches_before_fitness(self, engine: RuleEngine) -> None:
        """'fitness dk' (10 chars) beats 'fitness' (7 chars)."""
        result = engine.match("FITNESS DK Vesterbro", amount=-299.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Fitness/sport"][0]

    def test_escobar_matches_before_bar(self, engine: RuleEngine) -> None:
        """'escobar' (7 chars) beats 'bar' (3 chars)."""
        result = engine.match("Escobar Vestergade", amount=-85.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Barer/natteliv"][0]

    def test_kosem_restaurant_matches_before_restaurant(self, engine: RuleEngine) -> None:
        """'kosem restaurant' (16 chars) beats 'restaurant' (10 chars)."""
        result = engine.match("Kosem Restaurant Noerrebro", amount=-125.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Restaurant"][0]


# ──────────────────────────────────────────────
# Sign-dependent overrides
# ──────────────────────────────────────────────


class TestSignOverrides:
    def test_renter_positive_maps_to_income(self, engine: RuleEngine) -> None:
        result = engine.match("Renter kreditkonto", amount=12.50)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteindtaegter"][0]
        assert result.category_id == LOOKUP["Renteindtaegter"][1]

    def test_renter_negative_maps_to_expense(self, engine: RuleEngine) -> None:
        result = engine.match("Renter kreditkonto", amount=-12.50)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteudgifter"][0]
        assert result.category_id == LOOKUP["Renteudgifter"][1]

    def test_rente_positive_maps_to_income(self, engine: RuleEngine) -> None:
        result = engine.match("Rente opgoer Q4", amount=35.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteindtaegter"][0]

    def test_rente_negative_maps_to_expense(self, engine: RuleEngine) -> None:
        result = engine.match("Rente opgoer Q4", amount=-35.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Renteudgifter"][0]

    def test_mobilepay_positive_maps_to_ind(self, engine: RuleEngine) -> None:
        result = engine.match("MobilePay betaling", amount=200.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["MobilePay ind"][0]

    def test_mobilepay_negative_maps_to_ud(self, engine: RuleEngine) -> None:
        result = engine.match("MobilePay betaling", amount=-200.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["MobilePay ud"][0]

    def test_mobilepay_ind_explicit_always_ind(self, engine: RuleEngine) -> None:
        """Explicit 'mobilepay ind' keyword is longer, matches regardless of amount sign."""
        result = engine.match("MobilePay ind fra person", amount=-50.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["MobilePay ind"][0]

    def test_opsparing_positive_maps_to_ind(self, engine: RuleEngine) -> None:
        result = engine.match("Opsparing automatisk", amount=500.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Opsparing (ind)"][0]

    def test_opsparing_negative_maps_to_ud(self, engine: RuleEngine) -> None:
        result = engine.match("Opsparing automatisk", amount=-500.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Opsparing (ud)"][0]

    def test_fra_opsparing_always_ind(self, engine: RuleEngine) -> None:
        """'fra opsparing' (14 chars) beats 'opsparing' (9 chars)."""
        result = engine.match("Fra opsparing konto", amount=-100.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Opsparing (ind)"][0]


# ──────────────────────────────────────────────
# Case insensitivity
# ──────────────────────────────────────────────


class TestCaseInsensitivity:
    def test_uppercase_description(self, engine: RuleEngine) -> None:
        result = engine.match("NETTO KOEBENHAVN S", amount=-150.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Dagligvarer"][0]

    def test_mixed_case_description(self, engine: RuleEngine) -> None:
        result = engine.match("Spotify Premium", amount=-99.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Abonnementer"][0]


# ──────────────────────────────────────────────
# No match / edge cases
# ──────────────────────────────────────────────


class TestNoMatch:
    def test_no_keyword_match_returns_none(self, engine: RuleEngine) -> None:
        result = engine.match("Random unknown store xyz", amount=-50.0)
        assert result is None

    def test_empty_description_returns_none(self, engine: RuleEngine) -> None:
        result = engine.match("", amount=-50.0)
        assert result is None


# ──────────────────────────────────────────────
# Result metadata
# ──────────────────────────────────────────────


class TestResultMetadata:
    def test_tier_is_rule(self, engine: RuleEngine) -> None:
        result = engine.match("Netto", amount=-50.0)

        assert result is not None
        assert result.tier == CategorizationTier.RULE

    def test_confidence_is_high(self, engine: RuleEngine) -> None:
        result = engine.match("Netto", amount=-50.0)

        assert result is not None
        assert result.confidence == Confidence.HIGH


# ──────────────────────────────────────────────
# Missing subcategory in lookup
# ──────────────────────────────────────────────


class TestMissingLookup:
    def test_unknown_subcategory_is_skipped(self) -> None:
        """If keyword maps to subcategory not in lookup, skip and try next."""
        keywords = [
            ("phantom", "NonexistentCategory"),
            ("netto", "Dagligvarer"),
        ]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("phantom netto", amount=-50.0)

        assert result is not None
        assert result.subcategory_id == LOOKUP["Dagligvarer"][0]

    def test_all_unknown_returns_none(self) -> None:
        keywords = [("phantom", "NonexistentCategory")]
        engine = RuleEngine(keyword_mappings=keywords, subcategory_lookup=LOOKUP)

        result = engine.match("phantom transaction", amount=-50.0)
        assert result is None
