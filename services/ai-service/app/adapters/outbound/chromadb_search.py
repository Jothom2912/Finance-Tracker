"""ChromaDB semantic search adapter.

Implements ISemanticSearchPort by translating domain-level `filters` dict
into ChromaDB's `where` clause syntax. This is the single point where
domain vocabulary becomes implementation vocabulary:

    Domain filters                  →  ChromaDB where clause
    ─────────────────────────────────────────────────────────
    {"category": "dagligvarer"}     →  {"category": "dagligvarer"}
    {"amount": {"$lte": 200}}       →  {"amount": {"$lte": 200}}
    {"is_expense": True}            →  {"is_expense": True}
    period="2026-04"                →  {"year_month": "2026-04"}

    Multiple filters are combined with $and.
    user_id is always injected from constructor for tenant isolation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.adapters.outbound.vectorstore import embed_texts, get_collection
from app.domain.models import TransactionItem

logger = logging.getLogger(__name__)


class ChromaDBSearch:
    def __init__(self, user_id: int) -> None:
        self._user_id = user_id

    def search(
        self,
        query: str,
        *,
        period: str | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> tuple[list[TransactionItem], float]:
        """Hybrid search: semantic embedding query + metadata filters.

        Returns (items, elapsed_ms).
        """
        t0 = time.perf_counter()
        collection = get_collection()
        where = self._build_where(period, filters)
        query_embedding = embed_texts([query])[0]

        results = collection.query(
            query_embeddings=[query_embedding],
            where=where,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        metadatas = results.get("metadatas", [[]])[0]
        items = [self._to_item(m) for m in metadatas]
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info("ChromaDB search returned %d results in %.0fms", len(items), elapsed_ms)
        return items, elapsed_ms

    def _build_where(
        self,
        period: str | None,
        filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Translate domain filters + period into ChromaDB where clause.

        --- Domain→ChromaDB boundary ---
        This is where domain-level filter keys become ChromaDB `where` syntax.
        user_id is always injected from constructor for tenant isolation and
        must not be passed by caller — a mismatched user_id is a dispatcher bug.
        """
        clauses: list[dict[str, Any]] = [{"user_id": self._user_id}]

        if period:
            clauses.append({"year_month": period})

        if filters:
            for key, value in filters.items():
                if key == "user_id" and value != self._user_id:
                    raise ValueError(
                        f"Filter user_id={value} conflicts with constructor "
                        f"user_id={self._user_id}. user_id is auto-injected, "
                        "must not be passed by caller."
                    )
                if key == "user_id":
                    continue
                clauses.append({key: value})

        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _to_item(meta: dict[str, Any]) -> TransactionItem:
        return TransactionItem(
            id=int(meta.get("transaction_id", 0)),
            date=meta.get("date", ""),
            amount=float(meta.get("amount", 0.0)),
            category=meta.get("category", "Ukategoriseret"),
            description=meta.get("description", ""),
        )
