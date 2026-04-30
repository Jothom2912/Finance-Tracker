"""Unit tests for the RuleEngine adapter (tier 1 keyword matching)."""

from __future__ import annotations

import pytest
from app.adapters.outbound.rule_engine import RuleEngine
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
        result = engine.match("Netto Nordhavn", -150.0)
        assert result is not None
        assert result.subcategory_id == 1
        assert result.category_id == 1
        assert result.tier == CategorizationTier.RULE
        assert result.confidence == Confidence.HIGH

    def test_no_match_returns_none(self, engine: RuleEngine) -> None:
        result = engine.match("Unknown merchant XYZ", -50.0)
        assert result is None

    def test_case_insensitive(self, engine: RuleEngine) -> None:
        result = engine.match("NETTO CITY", -100.0)
        assert result is not None
        assert result.subcategory_id == 1


class TestLongestMatchFirst:
    def test_dsb_7eleven_beats_dsb(self, engine: RuleEngine) -> None:
        result = engine.match("DSB 7-Eleven Koebenhavn H", -45.0)
        assert result is not None
        assert result.subcategory_id == 3  # Kiosk, not Offentlig transport

    def test_plain_dsb_matches_transport(self, engine: RuleEngine) -> None:
        result = engine.match("DSB Billet", -89.0)
        assert result is not None
        assert result.subcategory_id == 4  # Offentlig transport


class TestSignOverrides:
    def test_renter_positive_is_income(self, engine: RuleEngine) -> None:
        result = engine.match("Renter tilskrevet", 12.50)
        assert result is not None
        assert result.subcategory_id == 5  # Renteindtaegter

    def test_renter_negative_is_expense(self, engine: RuleEngine) -> None:
        result = engine.match("Renter beregnet", -8.25)
        assert result is not None
        assert result.subcategory_id == 6  # Renteudgifter

    def test_mobilepay_positive_is_inbound(self, engine: RuleEngine) -> None:
        result = engine.match("MobilePay fra Anders", 200.0)
        assert result is not None
        assert result.subcategory_id == 7  # MobilePay ind

    def test_mobilepay_negative_is_outbound(self, engine: RuleEngine) -> None:
        result = engine.match("MobilePay til pizzeria", -120.0)
        assert result is not None
        assert result.subcategory_id == 8  # MobilePay ud


class TestDanishNormalization:
    def test_oe_normalization(self, engine: RuleEngine) -> None:
        result = engine.match("Køb hos Netto", -75.0)
        assert result is not None
        assert result.subcategory_id == 1
