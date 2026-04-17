"""Unit tests for the TransactionSyncConsumer projection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from backend.consumers.transaction_sync import TransactionSyncConsumer


def _event_data(event_type: str = "transaction.created", **overrides: object) -> dict:
    base: dict[str, object] = {
        "event_type": event_type,
        "event_version": 1,
        "transaction_id": 42,
        "account_id": 1,
        "user_id": 7,
        "amount": "123.45",
        "transaction_type": "expense",
        "tx_date": "2026-01-15",
        "category_id": 3,
        "category": "Food",
        "description": "Groceries",
        "account_name": "Savings",
        "correlation_id": "corr-001",
        "timestamp": "2026-01-15T00:00:00+00:00",
    }
    if event_type == "transaction.updated":
        base["previous_amount"] = "100.00"
        base["previous_category"] = "Misc"
    if event_type == "transaction.deleted":
        # Deleted has a minimal payload
        base = {
            "event_type": event_type,
            "event_version": 1,
            "transaction_id": base["transaction_id"],
            "account_id": base["account_id"],
            "user_id": base["user_id"],
            "amount": base["amount"],
            "correlation_id": base["correlation_id"],
            "timestamp": base["timestamp"],
        }
    base.update(overrides)
    return base


def _make_consumer(session_factory: MagicMock | None = None) -> TransactionSyncConsumer:
    return TransactionSyncConsumer(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        db_session_factory=session_factory or MagicMock(),
    )


class TestQueueRouting:
    @pytest.mark.asyncio()
    async def test_uses_own_queue_name(self) -> None:
        consumer = _make_consumer()
        assert consumer._queue_name == "monolith.transaction_sync"

    @pytest.mark.asyncio()
    async def test_subscribes_to_transaction_wildcard(self) -> None:
        consumer = _make_consumer()
        assert consumer._routing_key == "transaction.*"


class TestTransactionCreated:
    @pytest.mark.asyncio()
    async def test_inserts_new_transaction(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(_event_data())

        session.add.assert_called_once()
        model = session.add.call_args[0][0]
        assert model.idTransaction == 42
        assert model.amount == Decimal("123.45")
        assert model.description == "Groceries"
        assert model.type == "expense"
        assert model.Category_idCategory == 3
        assert model.Account_idAccount == 1
        session.commit.assert_called_once()

    @pytest.mark.asyncio()
    async def test_upserts_on_replay(self) -> None:
        """Re-delivery of the same transaction.created must be idempotent."""
        existing_model = MagicMock()
        existing_model.idTransaction = 42

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = existing_model
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(_event_data(amount="999.00"))

        session.add.assert_not_called()
        assert existing_model.amount == Decimal("999.00")
        session.commit.assert_called_once()

    @pytest.mark.asyncio()
    async def test_persists_categorization_metadata(self) -> None:
        """Tier/confidence/subcategory_id from the event must land on
        the MySQL row — this is the last link in the tier-badge chain.
        """
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(
            _event_data(
                subcategory_id=77,
                categorization_tier="rule",
                categorization_confidence="high",
            ),
        )

        model = session.add.call_args[0][0]
        assert model.subcategory_id == 77
        assert model.categorization_tier == "rule"
        assert model.categorization_confidence == "high"

    @pytest.mark.asyncio()
    async def test_parses_tx_date_as_iso(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(_event_data(tx_date="2025-12-31"))

        model = session.add.call_args[0][0]
        assert model.date.date() == date(2025, 12, 31)

    @pytest.mark.asyncio()
    async def test_rollback_on_error(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.commit.side_effect = RuntimeError("DB error")
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        with pytest.raises(RuntimeError, match="DB error"):
            await consumer.handle(_event_data())

        session.rollback.assert_called_once()
        session.close.assert_called_once()


class TestTransactionUpdated:
    @pytest.mark.asyncio()
    async def test_updates_existing_row(self) -> None:
        existing = MagicMock()
        existing.idTransaction = 42

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = existing
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(
            _event_data(event_type="transaction.updated", amount="200.00"),
        )

        assert existing.amount == Decimal("200.00")
        session.add.assert_not_called()
        session.commit.assert_called_once()

    @pytest.mark.asyncio()
    async def test_inserts_when_missing(self) -> None:
        """Update before create is race-safe: falls back to insert."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(_event_data(event_type="transaction.updated"))

        session.add.assert_called_once()
        session.commit.assert_called_once()


class TestTransactionDeleted:
    @pytest.mark.asyncio()
    async def test_removes_existing_row(self) -> None:
        existing = MagicMock()

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = existing
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(_event_data(event_type="transaction.deleted"))

        session.delete.assert_called_once_with(existing)
        session.commit.assert_called_once()

    @pytest.mark.asyncio()
    async def test_skips_when_already_absent(self) -> None:
        """Idempotent: deleting an already-missing row is a no-op."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(_event_data(event_type="transaction.deleted"))

        session.delete.assert_not_called()
        session.commit.assert_not_called()


class TestUnknownEvents:
    @pytest.mark.asyncio()
    async def test_unknown_type_is_ignored(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle({"event_type": "transaction.exploded"})

        factory.assert_not_called()


class TestSessionLifecycle:
    @pytest.mark.asyncio()
    async def test_always_closes_session(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        factory = MagicMock(return_value=session)

        consumer = _make_consumer(factory)
        await consumer.handle(_event_data())

        session.close.assert_called_once()
