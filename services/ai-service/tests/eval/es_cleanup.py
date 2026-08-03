"""Delete the 66 known eval fixtures plus the classified P3-21 orphan from a disposable ES copy."""

from __future__ import annotations

import argparse
import os

import httpx

from .es_seed import ES_ID_OFFSET
from .fixtures import EVAL_TRANSACTIONS, EVAL_USER_ID, OTHER_USER_ID, OTHER_USER_TRANSACTIONS

ORPHAN_ID = 99_999_999


def validate_cleanup_target(index_alias: str, *, allow_live: bool = False) -> str:
    normalized = index_alias.strip().lower()
    if allow_live and normalized == "transactions":
        return normalized
    if not normalized.startswith("p321_"):
        raise ValueError("P3-21 cleanup target must be a disposable p321_ alias")
    return normalized


def cleanup(
    index_alias: str,
    *,
    es_url: str,
    allow_live: bool = False,
    confirm_physical_index: str | None = None,
) -> int:
    target = validate_cleanup_target(index_alias, allow_live=allow_live)
    fixture_ids = [transaction.id + ES_ID_OFFSET for transaction in [*EVAL_TRANSACTIONS, *OTHER_USER_TRANSACTIONS]]
    expected_ids = [*fixture_ids, ORPHAN_ID]
    with httpx.Client(base_url=es_url, timeout=30.0) as es:
        aliases = es.get(f"/_alias/{target}")
        aliases.raise_for_status()
        physical_indices = sorted(aliases.json())
        if len(physical_indices) != 1:
            raise RuntimeError(f"cleanup alias must resolve to exactly one physical index: {physical_indices}")
        if allow_live and physical_indices != [confirm_physical_index]:
            raise RuntimeError(
                f"live alias target changed: expected {confirm_physical_index!r}, found {physical_indices}"
            )
        response = es.post(f"/{target}/_mget", json={"ids": [str(item) for item in expected_ids]})
        response.raise_for_status()
        documents = response.json()["docs"]
        found = {int(document["_id"]): document.get("_source") for document in documents if document.get("found")}
        if set(found) != set(expected_ids):
            raise RuntimeError(f"cleanup manifest mismatch; found {len(found)} of {len(expected_ids)} documents")
        for transaction_id in fixture_ids:
            source = found[transaction_id]
            if source["transaction_id"] != transaction_id or source["user_id"] not in {EVAL_USER_ID, OTHER_USER_ID}:
                raise RuntimeError(f"fixture identity mismatch for {transaction_id}")
        orphan = found[ORPHAN_ID]
        if orphan != {
            "transaction_id": ORPHAN_ID,
            "subcategory_id": 1,
            "is_deleted": False,
            "category_name": "Mad & drikke",
            "category_id": 1,
            "updated_at": orphan.get("updated_at"),
            "categorization_tier": "rule",
            "subcategory_name": "Dagligvarer",
            "categorization_confidence": "high",
            "categorization_event_ts": orphan.get("categorization_event_ts"),
        }:
            raise RuntimeError("classified orphan body no longer matches the P3-21 evidence")
        lines = [f'{{"delete":{{"_index":"{target}","_id":"{transaction_id}"}}}}' for transaction_id in expected_ids]
        deleted = es.post(
            "/_bulk?refresh=true",
            content="\n".join(lines) + "\n",
            headers={"Content-Type": "application/x-ndjson"},
        )
        deleted.raise_for_status()
        payload = deleted.json()
        if payload.get("errors"):
            raise RuntimeError("one or more P3-21 manifest deletes failed")
    return len(expected_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True)
    parser.add_argument("--es-url", default=os.getenv("ES_URL", "http://localhost:9200"))
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--confirm-physical-index")
    args = parser.parse_args()
    if args.allow_live and not args.confirm_physical_index:
        parser.error("--allow-live requires --confirm-physical-index")
    deleted = cleanup(
        args.index,
        es_url=args.es_url,
        allow_live=args.allow_live,
        confirm_physical_index=args.confirm_physical_index,
    )
    print(f"Deleted {deleted} classified documents from alias {args.index}")


if __name__ == "__main__":
    main()
