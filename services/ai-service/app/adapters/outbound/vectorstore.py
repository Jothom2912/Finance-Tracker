"""ChromaDB vector store with Ollama embeddings."""

from __future__ import annotations

import logging
import re

import chromadb
import ollama

from app.config import settings

logger = logging.getLogger(__name__)

LEGACY_COLLECTION_NAME = "transactions"

_chroma: chromadb.ClientAPI | None = None
_ollama: ollama.Client | None = None
_legacy_warning_done = False


def get_collection_name() -> str:
    """Collection name versioned by embedding model.

    Embeddings from different models have different dimensions and are not
    comparable, so each model gets its own collection. Swapping the model
    creates a new (empty) collection instead of touching existing data —
    users must re-ingest after a model change. Characters ChromaDB disallows
    in collection names are replaced with '-'.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "-", settings.EMBEDDING_MODEL)
    return f"transactions__{sanitized}"


def get_chroma_client() -> chromadb.ClientAPI:
    global _chroma
    if _chroma is None:
        _chroma = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
        logger.info("ChromaDB initialized at %s", settings.CHROMADB_PATH)
    return _chroma


def get_collection() -> chromadb.Collection:
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=get_collection_name(),
        metadata={"hnsw:space": "cosine"},
    )
    _warn_if_legacy_data(client, collection)
    return collection


def _warn_if_legacy_data(client: chromadb.ClientAPI, collection: chromadb.Collection) -> None:
    """Warn once if data only exists in the legacy unversioned collection."""
    global _legacy_warning_done
    if _legacy_warning_done:
        return
    _legacy_warning_done = True
    try:
        if collection.count() > 0:
            return
        legacy = client.get_collection(LEGACY_COLLECTION_NAME)
        legacy_count = legacy.count()
    except Exception:
        return
    if legacy_count > 0:
        logger.warning(
            "Legacy collection '%s' has %d documents but versioned collection '%s' "
            "is empty — re-ingest transactions to embed them with model '%s'",
            LEGACY_COLLECTION_NAME,
            legacy_count,
            collection.name,
            settings.EMBEDDING_MODEL,
        )


def get_ollama_client() -> ollama.Client:
    global _ollama
    if _ollama is None:
        _ollama = ollama.Client(host=settings.OLLAMA_BASE_URL)
        logger.info("Ollama client initialized at %s", settings.OLLAMA_BASE_URL)
    return _ollama


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using the configured Ollama embedding model."""
    response = get_ollama_client().embed(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return response.embeddings
