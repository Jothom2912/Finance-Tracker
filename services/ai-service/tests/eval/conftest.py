"""Eval-harness plumbing: Ollama-gating, isolated ChromaDB, one-time ingest.

Eval tests are marked `eval` and excluded from the default `make test` run —
they need a live Ollama with the configured models. Run them with:

    OLLAMA_BASE_URL=http://localhost:11435 make test-eval

(11435 = compose-ollama's host port; ollama-pull has bge-m3 + qwen3:4b there.)
The retrieval eval needs EMBEDDING_MODEL; the intent eval needs
LLM_ROUTER_MODEL — each skips independently if its model is missing.
"""

from __future__ import annotations

import httpx
import pytest
from app.config import settings

from .fixtures import (
    EVAL_TRANSACTIONS,
    EVAL_USER_ID,
    OTHER_USER_ID,
    OTHER_USER_TRANSACTIONS,
)


def _available_models() -> list[str] | None:
    """Model names on the configured Ollama, or None if unreachable."""
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        return None
    return [m["name"] for m in resp.json().get("models", [])]


def _has_model(models: list[str], wanted: str) -> bool:
    # Ollama viser "bge-m3:latest" for "bge-m3".
    return any(name == wanted or name.split(":")[0] == wanted for name in models)


@pytest.fixture(scope="session")
def ollama_models() -> list[str]:
    models = _available_models()
    if models is None:
        pytest.skip(f"Ollama unreachable at {settings.OLLAMA_BASE_URL} — eval skipped")
    return models


@pytest.fixture(scope="session")
def embedding_model(ollama_models: list[str]) -> str:
    if not _has_model(ollama_models, settings.EMBEDDING_MODEL):
        pytest.skip(f"Embedding model {settings.EMBEDDING_MODEL!r} not pulled — retrieval eval skipped")
    return settings.EMBEDDING_MODEL


@pytest.fixture(scope="session")
def router_model(ollama_models: list[str]) -> str:
    if not _has_model(ollama_models, settings.LLM_ROUTER_MODEL):
        pytest.skip(f"Router model {settings.LLM_ROUTER_MODEL!r} not pulled — intent eval skipped")
    return settings.LLM_ROUTER_MODEL


@pytest.fixture(scope="session")
def eval_collection(
    tmp_path_factory: pytest.TempPathFactory,
    embedding_model: str,
) -> None:
    """Ingest the fixture dataset into a session-temporary ChromaDB."""
    from app.adapters.outbound import vectorstore
    from app.application.ingest_service import (
        _format_transaction_text,
        _make_doc_id,
        _make_metadata,
    )

    chroma_dir = tmp_path_factory.mktemp("eval-chromadb")
    # Isolér fra en evt. rigtig CHROMADB_PATH; nulstil den procesglobale klient.
    settings.CHROMADB_PATH = str(chroma_dir)
    vectorstore._chroma = None

    collection = vectorstore.get_collection()
    for user_id, transactions in (
        (EVAL_USER_ID, EVAL_TRANSACTIONS),
        (OTHER_USER_ID, OTHER_USER_TRANSACTIONS),
    ):
        documents = [_format_transaction_text(t) for t in transactions]
        collection.upsert(
            ids=[_make_doc_id(user_id, t.id) for t in transactions],
            documents=documents,
            embeddings=vectorstore.embed_texts(documents),
            metadatas=[_make_metadata(user_id, t) for t in transactions],
        )
