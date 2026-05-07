"""Ingest service — fetches transactions and embeds them into ChromaDB."""

from __future__ import annotations

import logging

from app.adapters.outbound.transaction_client import TransactionDTO, fetch_user_transactions
from app.adapters.outbound.vectorstore import embed_texts, get_collection

logger = logging.getLogger(__name__)

DANISH_MONTHS = {
    1: "januar", 2: "februar", 3: "marts", 4: "april",
    5: "maj", 6: "juni", 7: "juli", 8: "august",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}

CATEGORY_SYNONYMS = {
    "dagligvarer": "mad, indkoeb, supermarked, grocery, husholdning",
    "restaurant": "restaurant, cafe, takeaway, mad ude, spisested",
    "transport": "transport, tog, bus, pendlerkort, rejse",
    "bolig": "bolig, husleje, leje, hjem, faste udgifter",
    "underholdning": "underholdning, streaming, abonnement, film, serier",
    "toej": "toej, shopping, beklaedning, mode",
    "loen": "loen, indkomst, salaris, udbetaling",
}


def _category_context(category_name: str | None) -> str:
    if not category_name:
        return ""
    synonyms = CATEGORY_SYNONYMS.get(category_name.lower())
    if not synonyms:
        return ""
    return f" Relaterede ord: {synonyms}."


def _format_transaction_text(txn: TransactionDTO) -> str:
    """Build a rich text representation for embedding.

    More prose = better semantic signal for the embedding model.
    """
    type_label = "Udgift" if txn.transaction_type == "expense" else "Indkomst"
    amount_abs = abs(txn.amount)
    month_name = DANISH_MONTHS.get(txn.date.month, str(txn.date.month))
    date_str = f"{txn.date.day}. {month_name} {txn.date.year}"

    category_part = ""
    if txn.category_name:
        category_part = f" Kategori: {txn.category_name}.{_category_context(txn.category_name)}"

    desc_part = ""
    if txn.description:
        desc_part = f" hos {txn.description}"

    return (
        f"{type_label} paa {amount_abs:.2f} kr{desc_part} "
        f"den {date_str}.{category_part}"
    )


def _make_doc_id(user_id: int, transaction_id: int) -> str:
    return f"user:{user_id}:txn:{transaction_id}"


def _make_metadata(user_id: int, txn: TransactionDTO) -> dict:
    return {
        "user_id": user_id,
        "transaction_id": txn.id,
        "date": txn.date.isoformat(),
        "year_month": txn.date.strftime("%Y-%m"),
        "amount": float(txn.amount),
        "category": txn.category_name or "Ukategoriseret",
        "is_expense": txn.transaction_type == "expense",
        "description": txn.description or "",
    }


async def ingest_transactions(user_id: int, token: str) -> int:
    """Fetch user's transactions and upsert them into ChromaDB.

    Returns the number of transactions ingested.
    """
    transactions = await fetch_user_transactions(token)

    if not transactions:
        logger.info("No transactions found for user %d", user_id)
        return 0

    collection = get_collection()

    doc_ids = [_make_doc_id(user_id, t.id) for t in transactions]
    documents = [_format_transaction_text(t) for t in transactions]
    metadatas = [_make_metadata(user_id, t) for t in transactions]

    batch_size = 50
    total = len(transactions)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_docs = documents[start:end]
        batch_ids = doc_ids[start:end]
        batch_meta = metadatas[start:end]

        embeddings = embed_texts(batch_docs)

        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            embeddings=embeddings,
            metadatas=batch_meta,
        )
        logger.info("Ingested batch %d-%d of %d", start, end, total)

    logger.info("Ingest complete: %d transactions for user %d", total, user_id)
    return total
