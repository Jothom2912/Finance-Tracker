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
async def test_dimension_mismatch_recreates_collection(
    mock_embed: MagicMock,
    mock_get_collection: MagicMock,
    mock_fetch: MagicMock,
) -> None:
    mock_fetch.return_value = [_make_transaction()]

    old_collection = MagicMock()
    new_collection = MagicMock()

    old_collection.peek.return_value = {
        "embeddings": [[0.1, 0.2, 0.3]],
    }

    call_count = 0

    def _get_collection_side_effect():
        nonlocal call_count
        call_count += 1
        return old_collection if call_count == 1 else new_collection

    mock_get_collection.side_effect = _get_collection_side_effect

    mock_embed.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]

    with patch(
        "app.adapters.outbound.vectorstore.get_chroma_client",
    ) as mock_chroma_client:
        result = await ingest_transactions(user_id=1, token="test-token")

    mock_chroma_client.return_value.delete_collection.assert_called_once()

    assert call_count == 2
    new_collection.upsert.assert_called_once()
    assert result == 1


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
async def test_no_transactions_returns_zero(
    mock_fetch: MagicMock,
) -> None:
    mock_fetch.return_value = []
    result = await ingest_transactions(user_id=1, token="test-token")
    assert result == 0
