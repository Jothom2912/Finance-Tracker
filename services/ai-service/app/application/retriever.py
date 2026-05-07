"""Retriever — searches ChromaDB for relevant transactions."""

from __future__ import annotations

import logging
import re

from app.adapters.outbound.vectorstore import embed_texts, get_collection
from app.config import settings

logger = logging.getLogger(__name__)

MONTH_MAP: dict[str, str] = {
    "januar": "01", "februar": "02", "marts": "03", "april": "04",
    "maj": "05", "juni": "06", "juli": "07", "august": "08",
    "september": "09", "oktober": "10", "november": "11", "december": "12",
}

_MONTH_PATTERN = re.compile(
    r"\b(" + "|".join(MONTH_MAP.keys()) + r")\b",
    re.IGNORECASE,
)
_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
_EXPENSE_PATTERN = re.compile(
    r"\b(brugte|brugt|udgift|udgifter|forbrug|betalte|kostede|spenderede)\b",
    re.IGNORECASE,
)


def _parse_date_hints(question: str) -> str | None:
    """Try to extract a year_month filter from the question.

    Returns a string like "2026-04" or None if no confident match.
    """
    month_match = _MONTH_PATTERN.search(question)
    year_match = _YEAR_PATTERN.search(question)

    if month_match:
        month_num = MONTH_MAP[month_match.group(1).lower()]
        year = year_match.group(1) if year_match else "2026"
        return f"{year}-{month_num}"

    return None


def _is_expense_question(question: str) -> bool:
    return bool(_EXPENSE_PATTERN.search(question))


def _build_where_filter(question: str, user_id: int) -> dict:
    filters = [{"user_id": user_id}]

    year_month = _parse_date_hints(question)
    if year_month:
        filters.append({"year_month": year_month})
        logger.info("Date filter applied: year_month=%s", year_month)

    if _is_expense_question(question):
        filters.append({"is_expense": True})
        logger.info("Expense filter applied")

    if len(filters) == 1:
        return filters[0]

    return {"$and": filters}


def retrieve(
    question: str,
    user_id: int,
    top_k: int | None = None,
) -> list[dict]:
    """Retrieve relevant transactions for a user's question.

    Always filters by user_id. Optionally adds year_month filter
    when a month name is detected in the question.

    Returns a list of dicts with 'document', 'metadata', and 'distance'.
    """
    if top_k is None:
        top_k = settings.RETRIEVAL_TOP_K

    collection = get_collection()

    where_filter = _build_where_filter(question, user_id)

    query_embedding = embed_texts([question])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        where=where_filter,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        retrieved.append({
            "document": doc,
            "metadata": meta,
            "distance": dist,
        })

    logger.info(
        "Retrieved %d results for user %d (filter: %s)",
        len(retrieved),
        user_id,
        where_filter,
    )
    return retrieved
