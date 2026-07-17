"""Shared Ollama client singleton for router/responder chat calls.

(Boede tidligere i vectorstore.py; overlevede ChromaDB-sletningen fordi
chat-adapterne stadig taler med Ollama via python-pakken. Query-embedding
i es_search.py bruger httpx direkte og er uafhængig af denne.)
"""

from __future__ import annotations

import logging

import ollama

from app.config import settings

logger = logging.getLogger(__name__)

_ollama: ollama.Client | None = None


def get_ollama_client() -> ollama.Client:
    global _ollama
    if _ollama is None:
        _ollama = ollama.Client(host=settings.OLLAMA_BASE_URL)
        logger.info("Ollama client initialized at %s", settings.OLLAMA_BASE_URL)
    return _ollama
