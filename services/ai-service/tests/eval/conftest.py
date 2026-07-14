"""Eval-harness plumbing: Ollama-gating, isolated ChromaDB, one-time ingest.

Eval tests are marked `eval` and excluded from the default `make test` run —
they need a live Ollama with the configured models. Run them with:

    OLLAMA_BASE_URL=http://localhost:11435 make test-eval

(11435 = compose-ollama's host port; ollama-pull has bge-m3 + qwen3:4b there.)
The retrieval eval needs EMBEDDING_MODEL; the intent eval needs
LLM_ROUTER_MODEL — each skips independently if its model is missing.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.adapters.outbound.chromadb_search import ChromaDBSearch
from app.application.ports.semantic_search_port import ISemanticSearchPort
from app.config import settings

from .es_seed import ES_ID_OFFSET
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
def search_factory(request: pytest.FixtureRequest) -> Callable[[int], ISemanticSearchPort]:
    """Backend-valg for retrieval-evalen — styret af SEARCH_BACKEND som i prod.

    chroma: fixtures ingestes i en session-temporær ChromaDB (som hidtil).
    es: kræver compose-stakken + seedede/embeddede eval-docs — se
    tests/eval/es_seed.py for flowet. Skipper med instruks hvis noget mangler.
    """
    if settings.SEARCH_BACKEND == "es":
        return _es_search_factory(request)
    request.getfixturevalue("eval_collection")
    return lambda user_id: ChromaDBSearch(user_id=user_id)


def _make_eval_jwt(user_id: int) -> str:
    from jose import jwt as jose_jwt

    return jose_jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) + timedelta(minutes=30)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


class _OffsetSearch:
    """De-offsetter ES-ids (es_seed.ES_ID_OFFSET) tilbage til fixture-ids."""

    def __init__(self, inner: ISemanticSearchPort) -> None:
        self._inner = inner

    def search(self, query: str, **kwargs: Any) -> tuple[list[Any], float]:
        items, elapsed_ms = self._inner.search(query, **kwargs)
        return [i.model_copy(update={"id": i.id - ES_ID_OFFSET}) for i in items], elapsed_ms


def _es_search_factory(request: pytest.FixtureRequest) -> Callable[[int], ISemanticSearchPort]:
    from app.adapters.outbound.es_search import EsSearch

    probe = EsSearch(user_id=EVAL_USER_ID, token=_make_eval_jwt(EVAL_USER_ID))
    if probe._embed_query("probe") is None:
        # Uden query-vektor ville evalen tavst måle BM25-only — skip højlydt.
        pytest.skip(f"Ollama query-embed utilgængelig ({settings.OLLAMA_BASE_URL}) — ES-eval ville være BM25-only")
    try:
        items, _ = probe.search("Netto", top_k=3)
    except Exception as exc:
        pytest.skip(f"analytics-service utilgængelig for ES-eval ({exc}) — er compose-stakken oppe?")
    if not items:
        pytest.skip("Ingen eval-docs i ES — kør: uv run python -m tests.eval.es_seed")

    es_url = os.getenv("ES_URL", "http://localhost:9200")
    count = httpx.post(
        f"{es_url}/transactions/_count",
        json={
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"user_id": EVAL_USER_ID}},
                        {"exists": {"field": "description_vector"}},
                    ]
                }
            }
        },
        timeout=10.0,
    ).json()["count"]
    if count == 0:
        pytest.skip(
            "Eval-docs mangler embeddings — kør: docker compose run --rm analytics-service "
            "python -m app.tools.backfill_embeddings --user-id 9001 --user-id 9002"
        )

    return lambda user_id: _OffsetSearch(EsSearch(user_id=user_id, token=_make_eval_jwt(user_id)))


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
