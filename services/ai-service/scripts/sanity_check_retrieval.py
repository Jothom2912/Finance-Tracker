"""Sanity check for retrieval quality — run BEFORE building the chat endpoint.

Usage (with Ollama running locally):
    OLLAMA_BASE_URL=http://localhost:11434 CHROMADB_PATH=./test_chromadb uv run python scripts/sanity_check_retrieval.py

This script:
1. Creates fake transactions
2. Ingests them into a test ChromaDB collection
3. Runs 10 test queries and prints what gets retrieved
4. Verifies user isolation (user A cannot see user B's data)
5. Cleans up the test collection
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.outbound.transaction_client import TransactionDTO  # noqa: E402
from app.adapters.outbound.vectorstore import embed_texts, get_collection  # noqa: E402
from app.application.ingest_service import _format_transaction_text, _make_doc_id, _make_metadata  # noqa: E402
from app.application.retriever import retrieve  # noqa: E402

SAMPLE_TRANSACTIONS_USER_1 = [
    TransactionDTO(id=1, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Dagligvarer", amount=Decimal("-287.50"), transaction_type="expense", description="Netto", date=date(2026, 4, 15)),
    TransactionDTO(id=2, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Dagligvarer", amount=Decimal("-412.00"), transaction_type="expense", description="Foetex", date=date(2026, 4, 18)),
    TransactionDTO(id=3, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Restaurant", amount=Decimal("-189.00"), transaction_type="expense", description="Dalle Valle", date=date(2026, 4, 20)),
    TransactionDTO(id=4, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Transport", amount=Decimal("-350.00"), transaction_type="expense", description="DSB Pendlerkort", date=date(2026, 3, 1)),
    TransactionDTO(id=5, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Underholdning", amount=Decimal("-149.00"), transaction_type="expense", description="Netflix", date=date(2026, 4, 5)),
    TransactionDTO(id=6, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Loen", amount=Decimal("28500.00"), transaction_type="income", description="Loenoverfoersel", date=date(2026, 4, 1)),
    TransactionDTO(id=7, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Bolig", amount=Decimal("-6500.00"), transaction_type="expense", description="Husleje", date=date(2026, 4, 1)),
    TransactionDTO(id=8, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Dagligvarer", amount=Decimal("-156.75"), transaction_type="expense", description="Rema 1000", date=date(2026, 3, 28)),
    TransactionDTO(id=9, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Toej", amount=Decimal("-899.00"), transaction_type="expense", description="H&M", date=date(2026, 4, 10)),
    TransactionDTO(id=10, user_id=1, account_id=1, account_name="Hovedkonto", category_name="Restaurant", amount=Decimal("-245.00"), transaction_type="expense", description="McDonalds", date=date(2026, 3, 15)),
]

SAMPLE_TRANSACTIONS_USER_2 = [
    TransactionDTO(id=11, user_id=2, account_id=2, account_name="Privatkonto", category_name="Dagligvarer", amount=Decimal("-500.00"), transaction_type="expense", description="Bilka", date=date(2026, 4, 12)),
]


def ingest_test_data(user_id: int, transactions: list[TransactionDTO]) -> None:
    collection = get_collection()
    doc_ids = [_make_doc_id(user_id, t.id) for t in transactions]
    documents = [_format_transaction_text(t) for t in transactions]
    metadatas = [_make_metadata(user_id, t) for t in transactions]
    embeddings = embed_texts(documents)

    collection.upsert(
        ids=doc_ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print(f"Ingested {len(transactions)} transactions for user {user_id}")
    print()
    print("Sample embedded texts:")
    for doc in documents[:3]:
        print(f"  -> {doc}")
    print()


def run_query(question: str, user_id: int, top_k: int = 5) -> None:
    results = retrieve(question, user_id, top_k=top_k)
    print(f'Q: "{question}" (user={user_id}, top_k={top_k})')
    if not results:
        print("  No results found")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [dist={r['distance']:.4f}] {r['document']}")
        print(f"     meta: category={r['metadata']['category']}, date={r['metadata']['date']}")
    print()


def main() -> None:
    print("=" * 60)
    print("SANITY CHECK: Retrieval Quality")
    print("=" * 60)
    print()

    ingest_test_data(1, SAMPLE_TRANSACTIONS_USER_1)
    ingest_test_data(2, SAMPLE_TRANSACTIONS_USER_2)

    print("=" * 60)
    print("TEST QUERIES")
    print("=" * 60)
    print()

    run_query("Netto", user_id=1)
    run_query("dagligvarer", user_id=1)
    run_query("supermarked mad indkoeb", user_id=1)
    run_query("restauranter", user_id=1)
    run_query("hvad brugte jeg i april", user_id=1)
    run_query("transport", user_id=1)
    run_query("husleje bolig", user_id=1)
    run_query("stoerste udgift", user_id=1)
    run_query("indkomst loen", user_id=1)

    print("=" * 60)
    print("USER ISOLATION TEST")
    print("=" * 60)
    print()
    results_user1 = retrieve("dagligvarer", user_id=1, top_k=10)
    results_user2 = retrieve("dagligvarer", user_id=2, top_k=10)

    user1_ids = {r["metadata"]["transaction_id"] for r in results_user1}
    user2_ids = {r["metadata"]["transaction_id"] for r in results_user2}
    overlap = user1_ids & user2_ids

    if overlap:
        print(f"FAIL: Cross-user leakage detected! Shared IDs: {overlap}")
    else:
        print("PASS: User isolation verified -- no cross-user data leakage")

    print(f"  User 1 got {len(results_user1)} results: IDs {user1_ids}")
    print(f"  User 2 got {len(results_user2)} results: IDs {user2_ids}")
    print()

    print("=" * 60)
    print("DATE FILTER TEST")
    print("=" * 60)
    print()
    run_query("hvad brugte jeg i april 2026", user_id=1)
    run_query("udgifter i marts", user_id=1)


if __name__ == "__main__":
    main()
