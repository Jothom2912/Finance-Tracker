"""Ollama-adapter for dokument-embeddings (AI-20, bge-m3).

Fejl her må aldrig nå projektions-køen — adapteren bruges kun af
embedding-consumeren (egen queue, egen DLQ), så exceptions propagerer
til dennes retry/DLQ-håndtering.
"""

from __future__ import annotations

import httpx

from app.adapters.outbound.elasticsearch.mappings import EMBEDDING_DIMS
from app.application.ports.outbound import IEmbeddingModelPort


class OllamaEmbedder(IEmbeddingModelPort):
    def __init__(self, base_url: str, model: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": text},
            )
            resp.raise_for_status()
        vector: list[float] = resp.json()["embeddings"][0]
        if len(vector) != EMBEDDING_DIMS:
            # Forkert model konfigureret — fail loudly frem for at skrive
            # vektorer der aldrig kan matches af query-siden.
            raise ValueError(f"Embedding har {len(vector)} dims, mapping kræver {EMBEDDING_DIMS} ({self._model})")
        return vector
