"""Contract test for TransactionCategorizedEvent.

Verifies the event schema matches what consumers expect.
"""

from __future__ import annotations

from contracts.events.transaction import TransactionCategorizedEvent


class TestTransactionCategorizedEvent:
    def test_event_type(self) -> None:
        event = TransactionCategorizedEvent(
            transaction_id=42,
            category_id=1,
            subcategory_id=1,
        )
        assert event.event_type == "transaction.categorized"
        assert event.event_version == 1

    def test_roundtrip_serialization(self) -> None:
        event = TransactionCategorizedEvent(
            transaction_id=42,
            category_id=1,
            subcategory_id=3,
            merchant_id=7,
            tier="rule",
            confidence="high",
            model_version="rules-keyword-v1",
        )
        json_str = event.to_json()
        restored = TransactionCategorizedEvent.from_json(json_str)

        assert restored.transaction_id == 42
        assert restored.category_id == 1
        assert restored.subcategory_id == 3
        assert restored.merchant_id == 7
        assert restored.tier == "rule"
        assert restored.confidence == "high"
        assert restored.model_version == "rules-keyword-v1"
        assert restored.correlation_id == event.correlation_id

    def test_optional_fields_default(self) -> None:
        event = TransactionCategorizedEvent(
            transaction_id=1,
            category_id=8,
            subcategory_id=32,
        )
        assert event.merchant_id is None
        assert event.tier == ""
        assert event.confidence == ""
        assert event.model_version == ""

    def test_unique_correlation_ids(self) -> None:
        a = TransactionCategorizedEvent(transaction_id=1, category_id=1, subcategory_id=1)
        b = TransactionCategorizedEvent(transaction_id=2, category_id=1, subcategory_id=1)
        assert a.correlation_id != b.correlation_id
