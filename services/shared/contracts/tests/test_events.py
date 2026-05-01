from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from contracts import (
    AccountCreatedEvent,
    AccountCreationFailedEvent,
    BudgetMonthClosedEvent,
    TransactionCreatedEvent,
    TransactionDeletedEvent,
    UserCreatedEvent,
    make_budget_month_closed_source_key,
)
from pydantic import ValidationError


class TestUserCreatedEvent:
    def test_serialization_roundtrip(self) -> None:
        event = UserCreatedEvent(user_id=1, email="a@b.com", username="alice")

        restored = UserCreatedEvent.from_json(event.to_json())

        assert restored.user_id == event.user_id
        assert restored.email == event.email
        assert restored.username == event.username
        assert restored.correlation_id == event.correlation_id
        assert restored.timestamp == event.timestamp

    def test_default_fields_populated(self) -> None:
        event = UserCreatedEvent(user_id=1, email="a@b.com", username="alice")

        assert event.correlation_id != ""
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_event_type_correctness(self) -> None:
        event = UserCreatedEvent(user_id=1, email="a@b.com", username="alice")

        assert event.event_type == "user.created"
        assert event.event_version == 1

    def test_immutability(self) -> None:
        event = UserCreatedEvent(user_id=1, email="a@b.com", username="alice")

        with pytest.raises(ValidationError):
            event.user_id = 999  # type: ignore[misc]

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            UserCreatedEvent()  # type: ignore[call-arg]

    def test_missing_single_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            UserCreatedEvent(user_id=1, email="a@b.com")  # type: ignore[call-arg]


class TestAccountCreatedEvent:
    def test_serialization_roundtrip(self) -> None:
        event = AccountCreatedEvent(account_id=10, user_id=1, account_name="Savings")

        restored = AccountCreatedEvent.from_json(event.to_json())

        assert restored.account_id == 10
        assert restored.user_id == 1
        assert restored.account_name == "Savings"
        assert restored.correlation_id == event.correlation_id

    def test_event_type_correctness(self) -> None:
        event = AccountCreatedEvent(account_id=10, user_id=1, account_name="Savings")

        assert event.event_type == "account.created"
        assert event.event_version == 1

    def test_immutability(self) -> None:
        event = AccountCreatedEvent(account_id=10, user_id=1, account_name="Savings")

        with pytest.raises(ValidationError):
            event.account_name = "Checking"  # type: ignore[misc]


class TestAccountCreationFailedEvent:
    def test_serialization_roundtrip(self) -> None:
        event = AccountCreationFailedEvent(user_id=1, reason="Duplicate account name")

        restored = AccountCreationFailedEvent.from_json(event.to_json())

        assert restored.user_id == 1
        assert restored.reason == "Duplicate account name"
        assert restored.correlation_id == event.correlation_id

    def test_event_type_correctness(self) -> None:
        event = AccountCreationFailedEvent(user_id=1, reason="Duplicate account name")

        assert event.event_type == "account.creation_failed"
        assert event.event_version == 1

    def test_immutability(self) -> None:
        event = AccountCreationFailedEvent(user_id=1, reason="Duplicate account name")

        with pytest.raises(ValidationError):
            event.reason = "other"  # type: ignore[misc]


class TestBudgetMonthClosedEvent:
    def test_serialization_roundtrip_preserves_decimal_strings(self) -> None:
        event = BudgetMonthClosedEvent(
            account_id=7,
            year=2026,
            month=4,
            budgeted_amount="5000.00",
            actual_spent="4200.10",
            surplus_amount="799.90",
        )

        restored = BudgetMonthClosedEvent.from_json(event.to_json())

        assert restored.account_id == 7
        assert restored.year == 2026
        assert restored.month == 4
        assert restored.budgeted_amount == "5000.00"
        assert restored.actual_spent == "4200.10"
        assert restored.surplus_amount == "799.90"
        assert restored.correlation_id == event.correlation_id

    def test_source_key_uses_account_year_and_month(self) -> None:
        event = BudgetMonthClosedEvent(
            account_id=7,
            year=2026,
            month=4,
            budgeted_amount="5000.00",
            actual_spent="4200.00",
            surplus_amount="800.00",
        )

        assert event.source_key == "budget.month_closed:7:2026:4"
        assert make_budget_month_closed_source_key(7, 2026, 4) == event.source_key

    def test_zero_amount_string_is_valid_and_preserved(self) -> None:
        event = BudgetMonthClosedEvent(
            account_id=7,
            year=2026,
            month=4,
            budgeted_amount="5000.00",
            actual_spent="5000.00",
            surplus_amount="0.00",
        )

        restored = BudgetMonthClosedEvent.from_json(event.to_json())

        assert restored.surplus_amount == "0.00"

    def test_event_type_correctness(self) -> None:
        event = BudgetMonthClosedEvent(
            account_id=7,
            year=2026,
            month=4,
            budgeted_amount="5000.00",
            actual_spent="4200.00",
            surplus_amount="800.00",
        )

        assert event.event_type == "budget.month_closed"
        assert event.event_version == 1

    @pytest.mark.parametrize("month", [0, 13])
    def test_invalid_month_raises(self, month: int) -> None:
        with pytest.raises(ValidationError):
            BudgetMonthClosedEvent(
                account_id=7,
                year=2026,
                month=month,
                budgeted_amount="5000.00",
                actual_spent="4200.00",
                surplus_amount="800.00",
            )

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(ValidationError):
            BudgetMonthClosedEvent(
                account_id=7,
                year=2026,
                month=4,
                budgeted_amount="5000.00",
                actual_spent="4200.00",
                surplus_amount="-1.00",
            )

    def test_non_decimal_amount_raises(self) -> None:
        with pytest.raises(ValidationError):
            BudgetMonthClosedEvent(
                account_id=7,
                year=2026,
                month=4,
                budgeted_amount="five thousand",
                actual_spent="4200.00",
                surplus_amount="800.00",
            )


class TestTransactionCreatedEvent:
    def test_serialization_roundtrip(self) -> None:
        event = TransactionCreatedEvent(
            transaction_id=42,
            account_id=1,
            user_id=7,
            amount="123.45",
            transaction_type="expense",
            tx_date=date(2026, 1, 15),
            category_id=3,
            category="Food",
            description="Groceries",
        )

        restored = TransactionCreatedEvent.from_json(event.to_json())

        assert restored.transaction_id == 42
        assert restored.account_id == 1
        assert restored.user_id == 7
        assert restored.amount == "123.45"
        assert restored.transaction_type == "expense"
        assert restored.tx_date == date(2026, 1, 15)
        assert restored.category_id == 3
        assert restored.category == "Food"
        assert restored.description == "Groceries"
        assert restored.correlation_id == event.correlation_id

    def test_event_type_correctness(self) -> None:
        event = TransactionCreatedEvent(
            transaction_id=1,
            account_id=1,
            user_id=1,
            amount="0.01",
            transaction_type="expense",
            tx_date=date(2026, 1, 1),
            category="Test",
            description="x",
        )

        assert event.event_type == "transaction.created"
        assert event.event_version == 1

    def test_amount_preserved_as_string(self) -> None:
        """Amount is kept as a string to avoid float precision loss."""
        event = TransactionCreatedEvent(
            transaction_id=1,
            account_id=1,
            user_id=1,
            amount="99999.99",
            transaction_type="income",
            tx_date=date(2026, 1, 1),
            category="Transfer",
            description="Large transfer",
        )

        restored = TransactionCreatedEvent.from_json(event.to_json())

        assert restored.amount == "99999.99"
        assert isinstance(restored.amount, str)

    def test_immutability(self) -> None:
        event = TransactionCreatedEvent(
            transaction_id=1,
            account_id=1,
            user_id=1,
            amount="10.00",
            transaction_type="expense",
            tx_date=date(2026, 1, 1),
            category="Test",
            description="x",
        )

        with pytest.raises(ValidationError):
            event.amount = "20.00"  # type: ignore[misc]

    def test_optional_fields_default_to_none_or_empty(self) -> None:
        event = TransactionCreatedEvent(
            transaction_id=1,
            account_id=1,
            user_id=1,
            amount="10.00",
            transaction_type="expense",
            tx_date=date(2026, 1, 1),
        )

        assert event.category_id is None
        assert event.category == ""
        assert event.description == ""
        assert event.subcategory_id is None
        assert event.categorization_tier is None


class TestTransactionDeletedEvent:
    def test_serialization_roundtrip(self) -> None:
        event = TransactionDeletedEvent(
            transaction_id=42,
            account_id=1,
            user_id=7,
            amount="50.00",
        )

        restored = TransactionDeletedEvent.from_json(event.to_json())

        assert restored.transaction_id == 42
        assert restored.account_id == 1
        assert restored.user_id == 7
        assert restored.amount == "50.00"
        assert restored.correlation_id == event.correlation_id

    def test_event_type_correctness(self) -> None:
        event = TransactionDeletedEvent(transaction_id=1, account_id=1, user_id=1, amount="0.01")

        assert event.event_type == "transaction.deleted"
        assert event.event_version == 1

    def test_immutability(self) -> None:
        event = TransactionDeletedEvent(transaction_id=1, account_id=1, user_id=1, amount="10.00")

        with pytest.raises(ValidationError):
            event.transaction_id = 999  # type: ignore[misc]


class TestBaseEvent:
    def test_unique_correlation_ids(self) -> None:
        event_a = UserCreatedEvent(user_id=1, email="a@b.com", username="a")
        event_b = UserCreatedEvent(user_id=2, email="c@d.com", username="b")

        assert event_a.correlation_id != event_b.correlation_id

    def test_timestamp_is_utc(self) -> None:
        event = UserCreatedEvent(user_id=1, email="a@b.com", username="alice")

        assert event.timestamp.tzinfo == timezone.utc

    def test_custom_correlation_id_preserved(self) -> None:
        event = UserCreatedEvent(
            user_id=1,
            email="a@b.com",
            username="alice",
            correlation_id="my-trace-id",
        )

        assert event.correlation_id == "my-trace-id"

    def test_to_json_returns_string(self) -> None:
        event = UserCreatedEvent(user_id=1, email="a@b.com", username="alice")

        result = event.to_json()

        assert isinstance(result, str)
        assert '"user_id":1' in result

    def test_from_json_invalid_data_raises(self) -> None:
        with pytest.raises(ValidationError):
            UserCreatedEvent.from_json('{"user_id": 1}')
