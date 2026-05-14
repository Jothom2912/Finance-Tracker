"""ChromaDB vector store with Ollama embeddings."""

from __future__ import annotations

import logging
import re

import chromadb
import ollama

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "transactions"

_chroma: chromadb.ClientAPI | None = None
_ollama: ollama.Client | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    global _chroma
    if _chroma is None:
        _chroma = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
        logger.info("ChromaDB initialized at %s", settings.CHROMADB_PATH)
    return _chroma


def get_collection() -> chromadb.Collection:
    client = get_chroma_client()
    model_slug = re.sub(r"[^a-zA-Z0-9]+", "-", settings.EMBEDDING_MODEL).strip("-").lower()
    collection_name = f"{COLLECTION_NAME}-{model_slug}" if model_slug else COLLECTION_NAME
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
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
