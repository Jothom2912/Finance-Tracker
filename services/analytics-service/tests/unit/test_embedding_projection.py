"""EmbeddingProjector: state-læsning, staleness-retry, guard-semantik (AI-20)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

import pytest
from app.application.embedding_projection import EmbeddingProjector, StaleProjectionError
from app.application.embedding_text import build_embedding_text
from app.application.ports.outbound import IEmbeddingModelPort, IEmbeddingStore
from contracts.events.transaction import (
    TransactionCategorizedEvent,
    TransactionCreatedEvent,
)

EVENT_TIME = datetime(2026, 7, 13, 12, 0, 0, tzinfo=UTC)
EVENT_TS = int(EVENT_TIME.timestamp() * 1000)


class FakeStore(IEmbeddingStore):
    def __init__(self, source: Optional[dict[str, Any]]) -> None:
        self.source = source
        self.updates: list[dict[str, Any]] = []

    async def get_projection(self, *, transaction_id: int) -> Optional[dict[str, Any]]:
        return self.source

    async def update_embedding(self, *, transaction_id: int, vector: list[float], event_ts: int) -> None:
        self.updates.append({"transaction_id": transaction_id, "vector": vector, "event_ts": event_ts})


class FakeEmbedder(IEmbeddingModelPort):
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return [0.1, 0.2]


def created_event() -> TransactionCreatedEvent:
    return TransactionCreatedEvent(
        transaction_id=42,
        account_id=1,
        user_id=7,
        amount="-287.50",
        transaction_type="expense",
        tx_date="2026-04-15",
        description="Netto",
        timestamp=EVENT_TIME,
    )


def doc(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "transaction_id": 42,
        "amount": -287.5,
        "transaction_type": "expense",
        "tx_date": "2026-04-15",
        "description": "Netto",
        "category_name": "Dagligvarer",
        "is_deleted": False,
        "updated_at": EVENT_TS,
    }
    return {**base, **overrides}


async def test_embeds_document_state_and_stamps_doc_updated_at() -> None:
    store = FakeStore(doc(updated_at=EVENT_TS + 500))
    embedder = FakeEmbedder()

    await EmbeddingProjector(store, embedder).handle(created_event())

    assert embedder.texts == [build_embedding_text(store.source)]
    (update,) = store.updates
    assert update["transaction_id"] == 42
    # Guard-ts er dokumentets updated_at (state-afledt), ikke eventets.
    assert update["event_ts"] == EVENT_TS + 500


async def test_missing_document_raises_stale_for_retry() -> None:
    store = FakeStore(None)

    with pytest.raises(StaleProjectionError):
        await EmbeddingProjector(store, FakeEmbedder()).handle(created_event())
    assert store.updates == []


async def test_document_older_than_event_raises_stale() -> None:
    store = FakeStore(doc(updated_at=EVENT_TS - 1))

    with pytest.raises(StaleProjectionError):
        await EmbeddingProjector(store, FakeEmbedder()).handle(created_event())


async def test_tombstone_is_silent_noop() -> None:
    store = FakeStore(doc(is_deleted=True))
    embedder = FakeEmbedder()

    await EmbeddingProjector(store, embedder).handle(created_event())

    assert embedder.texts == []
    assert store.updates == []


async def test_categorized_event_reembeds_merged_state() -> None:
    """Categorized bærer ikke beskrivelse/beløb — prosaen kommer fra dokumentet."""
    store = FakeStore(doc())
    embedder = FakeEmbedder()
    event = TransactionCategorizedEvent(
        transaction_id=42,
        category_id=3,
        category_name="Dagligvarer",
        subcategory_id=9,
        subcategory_name="Supermarked",
        timestamp=EVENT_TIME,
    )

    await EmbeddingProjector(store, embedder).handle(event)

    assert "Netto" in embedder.texts[0]
    assert "Dagligvarer" in embedder.texts[0]


class TestBuildEmbeddingText:
    def test_full_document(self) -> None:
        text = build_embedding_text(doc(subcategory_name="Supermarked"))
        assert text == (
            "Udgift paa 287.50 kr hos Netto den 15. april 2026. Kategori: Dagligvarer. Underkategori: Supermarked."
        )

    def test_income_by_type(self) -> None:
        text = build_embedding_text(doc(transaction_type="income", amount=28500.0, description="Loenoverfoersel"))
        assert text.startswith("Indkomst paa 28500.00 kr hos Loenoverfoersel")

    def test_income_by_sign_fallback_on_empty_type(self) -> None:
        assert build_embedding_text(doc(transaction_type="", amount=100.0)).startswith("Indkomst")
        assert build_embedding_text(doc(transaction_type="", amount=-100.0)).startswith("Udgift")

    def test_partial_document_categorized_before_created(self) -> None:
        # Kun felter fra categorized-eventet — må ikke crashe.
        text = build_embedding_text({"transaction_id": 42, "category_name": "Dagligvarer", "is_deleted": False})
        assert text == "Udgift. Kategori: Dagligvarer."
