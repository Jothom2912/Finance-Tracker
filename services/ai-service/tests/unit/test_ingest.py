"""Unit tests for ingest_service — verifies dimension mismatch detection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from app.adapters.outbound.transaction_client import TransactionDTO
from app.application.ingest_service import ingest_transactions


def _make_transaction(*, id: int = 1) -> TransactionDTO:
    return TransactionDTO(
        id=id,
        user_id=1,
        account_id=1,
        account_name="Test",
        amount=Decimal("99.50"),
        transaction_type="expense",
        description="Netto",
        category_name="dagligvarer",
        date=date(2026, 4, 15),
    )


@patch("app.application.ingest_service.fetch_user_transactions")
@patch("app.application.ingest_service.get_collection")
@patch("app.application.ingest_service.embed_texts")
async def test_dimension_mismatch_raises_without_deleting(
    mock_embed: MagicMock,
    mock_get_collection: MagicMock,
    mock_fetch: MagicMock,
) -> None:
    """Collections are versioned by model — a mismatch must fail loudly, never wipe data."""
    mock_fetch.return_value = [_make_transaction()]

    collection = MagicMock()
    collection.peek.return_value = {
        "embeddings": [[0.1, 0.2, 0.3]],
    }
    mock_get_collection.return_value = collection

    mock_embed.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]

    with pytest.raises(RuntimeError, match="dimension mismatch"):
        await ingest_transactions(user_id=1, token="test-token")

    collection.upsert.assert_not_called()


@patch("app.application.ingest_service.fetch_user_transactions")
@patch("app.application.ingest_service.get_collection")
@patch("app.application.ingest_service.embed_texts")
async def test_matching_dimensions_keeps_collection(
    mock_embed: MagicMock,
    mock_get_collection: MagicMock,
    mock_fetch: MagicMock,
) -> None:
    mock_fetch.return_value = [_make_transaction()]

    collection = MagicMock()
    collection.peek.return_value = {
        "embeddings": [[0.1, 0.2, 0.3]],
    }
    mock_get_collection.return_value = collection

    mock_embed.return_value = [[0.4, 0.5, 0.6]]

    result = await ingest_transactions(user_id=1, token="test-token")

    mock_get_collection.assert_called_once()
    collection.upsert.assert_called_once()
    assert result == 1


@patch("app.application.ingest_service.fetch_user_transactions")
@patch("app.application.ingest_service.get_collection")
@patch("app.application.ingest_service.embed_texts")
async def test_ingest_runs_blocking_work_off_event_loop(
    mock_embed: MagicMock,
    mock_get_collection: MagicMock,
    mock_fetch: MagicMock,
) -> None:
    """Embed + upsert must run in a worker thread, not on the event loop."""
    import threading

    mock_fetch.return_value = [_make_transaction(id=1), _make_transaction(id=2)]

    collection = MagicMock()
    collection.peek.return_value = {"embeddings": []}
    upsert_threads: list[int] = []
    upsert_kwargs: list[dict] = []

    def _record_upsert(**kwargs):
        upsert_threads.append(threading.get_ident())
        upsert_kwargs.append(kwargs)

    collection.upsert.side_effect = _record_upsert
    mock_get_collection.return_value = collection

    mock_embed.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    result = await ingest_transactions(user_id=1, token="test-token")

    assert result == 2
    assert upsert_threads and upsert_threads[0] != threading.get_ident()
    assert upsert_kwargs[0]["ids"] == ["user:1:txn:1", "user:1:txn:2"]


@patch("app.application.ingest_service.fetch_user_transactions")
async def test_no_transactions_returns_zero(
    mock_fetch: MagicMock,
) -> None:
    mock_fetch.return_value = []
    result = await ingest_transactions(user_id=1, token="test-token")
    assert result == 0
