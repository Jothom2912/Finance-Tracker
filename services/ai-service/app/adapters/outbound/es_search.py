"""ES hybrid search adapter (AI-20) — eneste semantic-search-backend
(ChromaDB slettet efter cutover-bake, plan 2026-07-12 trin 12).

Implements ISemanticSearchPort mod analytics-services hybrid-endpoint:
adapteren embedder selv queryen via Ollama (ai-service ejer query-sidens
embedding-model) og sender tekst + vektor; analytics-service ejer alle
ES-reads og fusionerer BM25+kNN med RRF.

    Domain filters                  →  hybrid-endpoint params
    ─────────────────────────────────────────────────────────
    {"category": "Dagligvarer"}     →  category_name (AI-21: → id)
    {"amount": {"$gte": 500}}       →  amount_min (på amount_abs)
    {"amount": {"$lte": 200}}       →  amount_max
    {"is_expense": True}            →  tx_type=expense
    period="2026-04"                →  start_date/end_date

Degradering: fejler query-embeddingen (Ollama nede/model mangler),
sendes queryen UDEN vektor — analytics-service svarer da BM25-only
frem for at chat-søgning dør (plan 2026-07-12 §Risks).

Sync (blocking) I/O per portens kontrakt — dispatcheren offloader via
anyio.to_thread.
"""

from __future__ import annotations

import calendar
import logging
import time
from typing import Any

import httpx

from app.adapters.outbound.analytics_client import _raise_for_status
from app.config import settings
from app.domain.models import TransactionItem

logger = logging.getLogger(__name__)


class EsSearch:
    def __init__(self, user_id: int, token: str) -> None:
        self._user_id = user_id
        self._token = token

    def search(
        self,
        query: str,
        *,
        period: str | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> tuple[list[TransactionItem], float]:
        """Hybrid search: BM25 + kNN via analytics-service. Returns (items, elapsed_ms)."""
        t0 = time.perf_counter()

        body: dict[str, Any] = {"query": query, "limit": top_k}
        body.update(self._translate(period, filters))

        vector = self._embed_query(query)
        if vector is not None:
            body["query_vector"] = vector

        resp = httpx.post(
            f"{settings.ANALYTICS_SERVICE_URL.rstrip('/')}/api/v1/analytics/search/hybrid",
            json=body,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=15.0,
        )
        _raise_for_status(resp)
        data = resp.json()

        items = [self._to_item(row) for row in data.get("items", [])]
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "ES hybrid search returned %d results in %.0fms (knn=%s)",
            len(items),
            elapsed_ms,
            data.get("used_knn"),
        )
        return items, elapsed_ms

    def _embed_query(self, query: str) -> list[float] | None:
        try:
            resp = httpx.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed",
                json={"model": settings.EMBEDDING_MODEL, "input": query},
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]
        except Exception:
            logger.warning("Query-embedding fejlede — degraderer til BM25-only", exc_info=True)
            return None

    def _translate(self, period: str | None, filters: dict[str, Any] | None) -> dict[str, Any]:
        """Domain-filtre → endpoint-params.

        --- Domain→analytics-API boundary ---
        user_id sendes ikke: analytics-service udleder tenant af JWT'en.
        Et user_id-filter der afviger fra konstruktørens er en
        dispatcher-bug.
        """
        params: dict[str, Any] = {}

        if period:
            year, month = int(period[:4]), int(period[5:7])
            last_day = calendar.monthrange(year, month)[1]
            params["start_date"] = f"{period}-01"
            params["end_date"] = f"{period}-{last_day:02d}"

        for key, value in (filters or {}).items():
            if key == "user_id":
                if value != self._user_id:
                    raise ValueError(
                        f"Filter user_id={value} conflicts with constructor "
                        f"user_id={self._user_id}. user_id is auto-injected, "
                        "must not be passed by caller."
                    )
            elif key == "category":
                params["category_name"] = value
            elif key == "amount":
                if "$gte" in value:
                    params["amount_min"] = float(value["$gte"])
                if "$lte" in value:
                    params["amount_max"] = float(value["$lte"])
            elif key == "is_expense":
                params["tx_type"] = "expense" if value else "income"
            else:
                logger.warning("Ukendt filter-nøgle %r ignoreres", key)

        return params

    @staticmethod
    def _to_item(row: dict[str, Any]) -> TransactionItem:
        return TransactionItem(
            id=int(row["id"]),
            date=str(row.get("date", "")),
            amount=float(row.get("amount", 0.0)),
            category=row.get("category_name") or "Ukategoriseret",
            description=row.get("description") or "",
        )
