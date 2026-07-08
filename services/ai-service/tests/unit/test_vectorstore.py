"""Unit tests for vectorstore — collection name versioned by embedding model."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.adapters.outbound.vectorstore import get_collection, get_collection_name
from app.config import settings


def test_collection_name_versioned_by_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "bge-m3")
    assert get_collection_name() == "transactions__bge-m3"


def test_collection_name_sanitizes_disallowed_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "qwen3:4b")
    assert get_collection_name() == "transactions__qwen3-4b"


@patch("app.adapters.outbound.vectorstore.get_chroma_client")
def test_get_collection_uses_versioned_name(
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingest and search both resolve the collection via get_collection,
    which must use the model-versioned name."""
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "bge-m3")
    get_collection()
    mock_client.return_value.get_or_create_collection.assert_called_once_with(
        name="transactions__bge-m3",
        metadata={"hnsw:space": "cosine"},
    )
