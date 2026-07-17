"""Unit tests for merchant-pattern normalization (F1-03)."""

from __future__ import annotations

from app.domain.merchant_normalization import MAX_PATTERN_LENGTH, normalize_merchant_pattern


class TestNormalizeMerchantPattern:
    def test_lowercases_and_transliterates_danish(self) -> None:
        assert normalize_merchant_pattern("FØTEX København") == "foetex koebenhavn"

    def test_drops_reference_numbers_so_same_merchant_converges(self) -> None:
        a = normalize_merchant_pattern("NETTO VESTERBRO 12345")
        b = normalize_merchant_pattern("NETTO VESTERBRO 99887")
        assert a == b == "netto vesterbro"

    def test_keeps_tokens_mixing_digits_and_letters(self) -> None:
        assert normalize_merchant_pattern("7-Eleven Hovedbanen") == "7-eleven hovedbanen"

    def test_rema_1000_learns_as_rema(self) -> None:
        """Documented v1 trade-off: the digit token drops, but 'rema'
        contains-matches future 'Rema 1000' rows anyway."""
        assert normalize_merchant_pattern("REMA 1000 Valby") == "rema valby"

    def test_digits_only_description_is_unlearnable(self) -> None:
        assert normalize_merchant_pattern("1234 5678") == ""

    def test_empty_and_whitespace_are_unlearnable(self) -> None:
        assert normalize_merchant_pattern("") == ""
        assert normalize_merchant_pattern("   ") == ""

    def test_collapses_whitespace(self) -> None:
        assert normalize_merchant_pattern("Netto   \t Vesterbro") == "netto vesterbro"

    def test_caps_length(self) -> None:
        assert len(normalize_merchant_pattern("butik " * 100)) <= MAX_PATTERN_LENGTH
