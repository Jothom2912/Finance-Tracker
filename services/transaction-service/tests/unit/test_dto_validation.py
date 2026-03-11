from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.application.dto import (
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    TransactionFiltersDTO,
)
from app.domain.entities import TransactionType


def _valid_tx(**overrides) -> dict:  # type: ignore[no-untyped-def]
    defaults = {
        "account_id": 1,
        "account_name": "Main",
        "amount": Decimal("100.00"),
        "transaction_type": TransactionType.EXPENSE,
        "date": date(2026, 3, 1),
    }
    defaults.update(overrides)
    return defaults


def _valid_planned(**overrides) -> dict:  # type: ignore[no-untyped-def]
    defaults = {
        "account_id": 1,
        "account_name": "Main",
        "amount": Decimal("100.00"),
        "transaction_type": TransactionType.EXPENSE,
        "recurrence": "monthly",
        "next_execution": date(2026, 4, 1),
    }
    defaults.update(overrides)
    return defaults


class TestAmountBoundaries:
    def test_at_minimum_valid(self) -> None:
        dto = CreateTransactionDTO(**_valid_tx(amount=Decimal("0.01")))
        assert dto.amount == Decimal("0.01")

    def test_below_minimum_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CreateTransactionDTO(**_valid_tx(amount=Decimal("0.00")))

    def test_at_maximum_valid(self) -> None:
        dto = CreateTransactionDTO(
            **_valid_tx(amount=Decimal("9999999999.99"))
        )
        assert dto.amount == Decimal("9999999999.99")

    def test_above_maximum_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CreateTransactionDTO(
                **_valid_tx(amount=Decimal("10000000000.00"))
            )

    def test_negative_amount_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CreateTransactionDTO(**_valid_tx(amount=Decimal("-1.00")))


class TestDescriptionBoundaries:
    def test_at_max_valid(self) -> None:
        dto = CreateTransactionDTO(
            **_valid_tx(description="x" * 500)
        )
        assert len(dto.description) == 500

    def test_above_max_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CreateTransactionDTO(**_valid_tx(description="x" * 501))


class TestAccountId:
    def test_zero_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CreateTransactionDTO(**_valid_tx(account_id=0))

    def test_positive_valid(self) -> None:
        dto = CreateTransactionDTO(**_valid_tx(account_id=1))
        assert dto.account_id == 1

    def test_negative_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CreateTransactionDTO(**_valid_tx(account_id=-1))


class TestTransactionTypeValidation:
    def test_income_valid(self) -> None:
        dto = CreateTransactionDTO(
            **_valid_tx(transaction_type=TransactionType.INCOME)
        )
        assert dto.transaction_type == TransactionType.INCOME

    def test_expense_valid(self) -> None:
        dto = CreateTransactionDTO(
            **_valid_tx(transaction_type=TransactionType.EXPENSE)
        )
        assert dto.transaction_type == TransactionType.EXPENSE

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            CreateTransactionDTO(**_valid_tx(transaction_type="transfer"))


class TestRecurrenceValidation:
    @pytest.mark.parametrize(
        "value",
        ["daily", "weekly", "biweekly", "monthly", "yearly"],
    )
    def test_valid_values(self, value: str) -> None:
        dto = CreatePlannedTransactionDTO(**_valid_planned(recurrence=value))
        assert dto.recurrence == value

    def test_invalid_value(self) -> None:
        with pytest.raises(ValidationError):
            CreatePlannedTransactionDTO(
                **_valid_planned(recurrence="bimonthly")
            )


class TestFiltersLimitBoundaries:
    def test_zero_limit_invalid(self) -> None:
        with pytest.raises(ValidationError):
            TransactionFiltersDTO(limit=0)

    def test_one_limit_valid(self) -> None:
        dto = TransactionFiltersDTO(limit=1)
        assert dto.limit == 1

    def test_max_limit_valid(self) -> None:
        dto = TransactionFiltersDTO(limit=200)
        assert dto.limit == 200

    def test_above_max_limit_invalid(self) -> None:
        with pytest.raises(ValidationError):
            TransactionFiltersDTO(limit=201)

    def test_negative_skip_invalid(self) -> None:
        with pytest.raises(ValidationError):
            TransactionFiltersDTO(skip=-1)
