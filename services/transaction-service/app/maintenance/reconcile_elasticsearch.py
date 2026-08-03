"""Fail-closed Postgres↔Elasticsearch transaction reconciliation (P3-21).

Reads transaction-service's authoritative live rows and one concrete ES alias.
It never writes either store. Exit status is non-zero for any ID, identity,
amount, alias, duplicate or pagination discrepancy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import psycopg2

PAGE_SIZE = 500
CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class TransactionFact:
    transaction_id: int
    user_id: int
    account_id: int
    category_id: int | None
    tx_date: str
    amount: Decimal

    def canonical(self) -> dict[str, int | str | None]:
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "category_id": self.category_id,
            "tx_date": self.tx_date,
            "amount": format(self.amount.quantize(CENT), "f"),
        }


def reconcile(source: list[TransactionFact], projected: list[TransactionFact]) -> dict[str, Any]:
    source_by_id = _unique(source, "Postgres")
    projected_by_id = _unique(projected, "Elasticsearch")
    source_ids = set(source_by_id)
    projected_ids = set(projected_by_id)
    shared_ids = source_ids & projected_ids
    field_mismatches = [
        {
            "transaction_id": transaction_id,
            "postgres": source_by_id[transaction_id].canonical(),
            "elasticsearch": projected_by_id[transaction_id].canonical(),
        }
        for transaction_id in sorted(shared_ids)
        if source_by_id[transaction_id] != projected_by_id[transaction_id]
    ]
    source_groups = _groups(source)
    projected_groups = _groups(projected)
    group_mismatches = {
        key: {"postgres": source_groups.get(key), "elasticsearch": projected_groups.get(key)}
        for key in sorted(set(source_groups) | set(projected_groups))
        if source_groups.get(key) != projected_groups.get(key)
    }
    report = {
        "schema_version": "transaction-es-reconciliation-v1",
        "postgres_count": len(source),
        "elasticsearch_count": len(projected),
        "missing_in_elasticsearch": sorted(source_ids - projected_ids),
        "extra_in_elasticsearch": sorted(projected_ids - source_ids),
        "field_mismatches": field_mismatches,
        "group_mismatches": group_mismatches,
        "postgres_hash": _hash(source),
        "elasticsearch_hash": _hash(projected),
    }
    report["reconciled"] = not any(
        (
            report["missing_in_elasticsearch"],
            report["extra_in_elasticsearch"],
            field_mismatches,
            group_mismatches,
        )
    )
    report["report_hash"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return report


def _unique(rows: list[TransactionFact], source: str) -> dict[int, TransactionFact]:
    result: dict[int, TransactionFact] = {}
    for row in rows:
        if row.transaction_id in result:
            raise ValueError(f"{source} contains duplicate transaction_id {row.transaction_id}")
        result[row.transaction_id] = row
    return result


def _groups(rows: list[TransactionFact]) -> dict[str, dict[str, int | str]]:
    aggregates: dict[str, tuple[int, Decimal]] = defaultdict(lambda: (0, Decimal("0")))
    for row in rows:
        keys = (
            "global",
            f"user:{row.user_id}",
            f"account:{row.account_id}",
            f"category:{row.category_id}",
            f"month:{row.tx_date[:7]}",
        )
        for key in keys:
            count, amount = aggregates[key]
            aggregates[key] = (count + 1, amount + row.amount)
    return {
        key: {"count": count, "amount": format(amount.quantize(CENT), "f")}
        for key, (count, amount) in sorted(aggregates.items())
    }


def _hash(rows: list[TransactionFact]) -> str:
    payload = [row.canonical() for row in sorted(rows, key=lambda item: item.transaction_id)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_postgres(database_url: str) -> list[TransactionFact]:
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg2.connect(sync_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id,user_id,account_id,category_id,date,amount FROM transactions "
            "WHERE deleted_at IS NULL ORDER BY id"
        )
        return [
            TransactionFact(
                transaction_id=row[0],
                user_id=row[1],
                account_id=row[2],
                category_id=row[3],
                tx_date=_date_string(row[4]),
                amount=Decimal(row[5]).quantize(CENT),
            )
            for row in cursor.fetchall()
        ]


def load_elasticsearch(es_url: str, alias: str) -> tuple[str, list[TransactionFact]]:
    with httpx.Client(base_url=es_url, timeout=30.0) as client:
        aliases = client.get(f"/_alias/{alias}")
        aliases.raise_for_status()
        physical_indices = sorted(aliases.json())
        if len(physical_indices) != 1:
            raise ValueError(f"alias {alias!r} must resolve to exactly one index: {physical_indices}")
        mapping = client.get(f"/{physical_indices[0]}/_mapping")
        mapping.raise_for_status()
        properties = mapping.json()[physical_indices[0]]["mappings"].get("properties", {})
        required = {"transaction_id", "user_id", "account_id", "category_id", "tx_date", "amount", "is_deleted"}
        if not required <= set(properties):
            raise ValueError(f"transaction mapping misses fields: {sorted(required - set(properties))}")

        pit_response = client.post(f"/{alias}/_pit", params={"keep_alive": "1m"})
        pit_response.raise_for_status()
        pit_id = pit_response.json()["id"]
        rows: list[TransactionFact] = []
        search_after: list[Any] | None = None
        expected_total: int | None = None
        try:
            while True:
                body: dict[str, Any] = {
                    "size": PAGE_SIZE,
                    "track_total_hits": True,
                    "pit": {"id": pit_id, "keep_alive": "1m"},
                    "query": {"term": {"is_deleted": False}},
                    "sort": [{"transaction_id": "asc"}, {"_shard_doc": "asc"}],
                    "_source": [
                        "transaction_id",
                        "user_id",
                        "account_id",
                        "category_id",
                        "tx_date",
                        "amount",
                    ],
                }
                if search_after is not None:
                    body["search_after"] = search_after
                response = client.post("/_search", json=body)
                response.raise_for_status()
                payload = response.json()
                pit_id = payload.get("pit_id", pit_id)
                total = payload["hits"]["total"]
                if total.get("relation") != "eq":
                    raise ValueError("Elasticsearch returned an inexact total")
                expected_total = int(total["value"]) if expected_total is None else expected_total
                if int(total["value"]) != expected_total:
                    raise ValueError("Elasticsearch total changed during pagination")
                hits = payload["hits"]["hits"]
                if not hits:
                    break
                for hit in hits:
                    source = hit["_source"]
                    required_source = {"transaction_id", "user_id", "account_id", "tx_date", "amount"}
                    missing_source = required_source - set(source)
                    if missing_source:
                        raise ValueError(f"Elasticsearch document {hit['_id']} misses fields: {sorted(missing_source)}")
                    rows.append(
                        TransactionFact(
                            transaction_id=int(source["transaction_id"]),
                            user_id=int(source["user_id"]),
                            account_id=int(source["account_id"]),
                            category_id=(int(source["category_id"]) if source.get("category_id") is not None else None),
                            tx_date=str(source["tx_date"]),
                            amount=Decimal(str(source["amount"])).quantize(CENT),
                        )
                    )
                search_after = hits[-1].get("sort")
                if not search_after:
                    raise ValueError("Elasticsearch pagination hit omitted sort values")
        finally:
            close_response = client.request("DELETE", "/_pit", json={"id": pit_id})
            close_response.raise_for_status()
        if expected_total != len(rows):
            raise ValueError(f"Elasticsearch pagination returned {len(rows)} of {expected_total} rows")
        return physical_indices[0], rows


def _date_string(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--es-url", default=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"))
    parser.add_argument("--alias", default="transactions")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    source = load_postgres(args.database_url)
    physical_index, projected = load_elasticsearch(args.es_url, args.alias)
    report = reconcile(source, projected)
    report["elasticsearch_alias"] = args.alias
    report["elasticsearch_index"] = physical_index
    print(json.dumps(report, sort_keys=True, indent=2))
    if not report["reconciled"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
