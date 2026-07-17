"""Seed eval-fixtures i compose-ES til ES-backend-eval (AI-20 cutover-gate).

Flow (fra services/ai-service, med compose-stakken oppe)::

    1. uv run python -m tests.eval.es_seed
    2. (fra repo-roden) docker compose run --rm analytics-service \\
           python -m app.tools.backfill_embeddings --user-id 9001 --user-id 9002
    3. make test-eval-retrieval

Skriver BEVIDST direkte i ES (udenom analytics-service): eval-brugerne
9001/9002 findes ikke i kildeservices, så event-/backfill-stien kan ikke
producere dem. Dokument-formen spejler transactions_v2-mappingen; drift
fanges af strict mapping (indexering fejler højlydt).

Transaction-ids offsettes med ES_ID_OFFSET så eval-docs aldrig kan
clobre rigtige dokumenter (_id = transaction_id). Genkørsel er
idempotent: sletter alle docs for eval-brugerne først (inkl. vektorer —
husk at køre backfill_embeddings igen efter reseed).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import httpx

from .fixtures import EVAL_TRANSACTIONS, EVAL_USER_ID, OTHER_USER_ID, OTHER_USER_TRANSACTIONS

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_ID_OFFSET = 9_000_000
# Fast, fortidig event-ts: et evt. rigtigt live-event ville vinde guards.
SEED_TS = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000)


def seed() -> None:
    with httpx.Client(base_url=ES_URL, timeout=30.0) as es:
        es.post(
            "/transactions/_delete_by_query?refresh=true&conflicts=proceed",
            json={"query": {"terms": {"user_id": [EVAL_USER_ID, OTHER_USER_ID]}}},
        ).raise_for_status()

        lines: list[str] = []
        for txn in [*EVAL_TRANSACTIONS, *OTHER_USER_TRANSACTIONS]:
            es_id = txn.id + ES_ID_OFFSET
            lines.append(f'{{"index": {{"_index": "transactions", "_id": "{es_id}"}}}}')
            doc = {
                "transaction_id": es_id,
                "account_id": txn.account_id,
                "user_id": txn.user_id,
                "amount": float(txn.amount),
                "amount_abs": abs(float(txn.amount)),
                "transaction_type": txn.transaction_type,
                "tx_date": txn.date.isoformat(),
                "description": txn.description,
                "category_id": None,
                "category_name": txn.category_name,
                "subcategory_id": None,
                "subcategory_name": None,
                "categorization_tier": None,
                "categorization_confidence": None,
                "is_deleted": False,
                "core_event_ts": SEED_TS,
                "updated_at": SEED_TS,
            }
            lines.append(json.dumps(doc))

        resp = es.post(
            "/_bulk?refresh=true",
            content="\n".join(lines) + "\n",
            headers={"Content-Type": "application/x-ndjson"},
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            failed = [i["index"] for i in body["items"] if i["index"].get("error")]
            raise SystemExit(f"Bulk-indexering fejlede for {len(failed)} docs: {failed[:3]}")

    total = len(EVAL_TRANSACTIONS) + len(OTHER_USER_TRANSACTIONS)
    print(f"Seedede {total} eval-docs (id-offset {ES_ID_OFFSET}) i {ES_URL}/transactions")
    print(
        "Næste skridt: docker compose run --rm analytics-service python -m app.tools.backfill_embeddings --user-id 9001 --user-id 9002"
    )


if __name__ == "__main__":
    seed()
