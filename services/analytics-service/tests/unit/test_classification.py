from __future__ import annotations

import enum

import pytest
from app.domain.classification import is_expense, is_income, normalize_tx_type


class _TxType(enum.Enum):
    EXPENSE = "expense"


class TestNormalizeTxType:
    def test_none_becomes_empty_string(self) -> None:
        assert normalize_tx_type(None) == ""

    def test_lowercases_string(self) -> None:
        assert normalize_tx_type("EXPENSE") == "expense"

    def test_unwraps_enum_value(self) -> None:
        assert normalize_tx_type(_TxType.EXPENSE) == "expense"


class TestIsExpense:
    def test_explicit_type_wins_regardless_of_sign(self) -> None:
        assert is_expense("expense", 100.0)
        assert is_expense("expense", -100.0)

    def test_income_type_is_never_expense(self) -> None:
        assert not is_expense("income", -100.0)

    @pytest.mark.parametrize(("amount", "expected"), [(-1.0, True), (1.0, False), (0.0, False)])
    def test_empty_type_falls_back_to_sign(self, amount: float, expected: bool) -> None:
        assert is_expense("", amount) is expected


class TestIsIncome:
    def test_explicit_type_wins_regardless_of_sign(self) -> None:
        assert is_income("income", -50.0)

    @pytest.mark.parametrize(("amount", "expected"), [(1.0, True), (-1.0, False), (0.0, False)])
    def test_empty_type_falls_back_to_sign(self, amount: float, expected: bool) -> None:
        assert is_income("", amount) is expected

    def test_zero_amount_without_type_is_neither(self) -> None:
        assert not is_income("", 0.0)
        assert not is_expense("", 0.0)
