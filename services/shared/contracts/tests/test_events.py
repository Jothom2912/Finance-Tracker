from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from contracts import (
    AccountCreatedEvent,
    AccountCreationFailedEvent,
    BaseEvent,
    TransactionCreatedEvent,
    TransactionDeletedEvent,
    UserCreatedEvent,
)


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
        event = AccountCreatedEvent(
            account_id=10, user_id=1, account_name="Savings"
        )

        restored = AccountCreatedEvent.from_json(event.to_json())

        assert restored.account_id == 10
        assert restored.user_id == 1
        assert restored.account_name == "Savings"
        assert restored.correlation_id == event.correlation_id

    def test_event_type_correctness(self) -> None:
        event = AccountCreatedEvent(
            account_id=10, user_id=1, account_name="Savings"
        )

        assert event.event_type == "account.created"
        assert event.event_version == 1

    def test_immutability(self) -> None:
        event = AccountCreatedEvent(
            account_id=10, user_id=1, account_name="Savings"
        )

        with pytest.raises(ValidationError):
            event.account_name = "Checking"  # type: ignore[misc]


class TestAccountCreationFailedEvent:
    def test_serialization_roundtrip(self) -> None:
        event = AccountCreationFailedEvent(
            user_id=1, reason="Duplicate account name"
        )

        restored = AccountCreationFailedEvent.from_json(event.to_json())

        assert restored.user_id == 1
        assert restored.reason == "Duplicate account name"
        assert restored.correlation_id == event.correlation_id

    def test_event_type_correctness(self) -> None:
        event = AccountCreationFailedEvent(
            user_id=1, reason="Duplicate account name"
        )

        assert event.event_type == "account.creation_failed"
        assert event.event_version == 1

    def test_immutability(self) -> None:
        event = AccountCreationFailedEvent(
            user_id=1, reason="Duplicate account name"
        )

        with pytest.raises(ValidationError):
            event.reason = "other"  # type: ignore[misc]


class TestTransactionCreatedEvent:
    def test_serialization_roundtrip(self) -> None:
        event = TransactionCreatedEvent(
            transaction_id=42,
            account_id=1,
            user_id=7,
            amount="123.45",
            category="Food",
            description="Groceries",
        )

        restored = TransactionCreatedEvent.from_json(event.to_json())

        assert restored.transaction_id == 42
        assert restored.account_id == 1
        assert restored.user_id == 7
        assert restored.amount == "123.45"
        assert restored.category == "Food"
        assert restored.description == "Groceries"
        assert restored.correlation_id == event.correlation_id

    def test_event_type_correctness(self) -> None:
        event = TransactionCreatedEvent(
            transaction_id=1,
            account_id=1,
            user_id=1,
            amount="0.01",
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
            category="Test",
            description="x",
        )

        with pytest.raises(ValidationError):
            event.amount = "20.00"  # type: ignore[misc]


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
        event = TransactionDeletedEvent(
            transaction_id=1, account_id=1, user_id=1, amount="0.01"
        )

        assert event.event_type == "transaction.deleted"
        assert event.event_version == 1

    def test_immutability(self) -> None:
        event = TransactionDeletedEvent(
            transaction_id=1, account_id=1, user_id=1, amount="10.00"
        )

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
