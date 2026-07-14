"""Index-definitioner for read-storen.

Konventioner (ADR-004):
- Fysisk index ``<prefix><navn>_v1`` bag alias ``<prefix><navn>``; alle
  læs/skriv går via alias, så reindex = opret v2 + swap alias.
- ``dynamic: strict`` så kontrakt-drift fejler højlydt i stedet for at
  forurene mappings.
- Beløb som ``scaled_float(100)``: øre-præcis heltalsmatematik i aggs.
  Events serialiserer beløb som decimal-strenge; stores parser med
  ``Decimal`` før skrivning.
- ``*_event_ts``-felter er idempotens-guards (epoch-millis af eventets
  timestamp), ikke domænedata.
"""

from __future__ import annotations

from typing import Any

_AMOUNT = {"type": "scaled_float", "scaling_factor": 100}
_TS = {"type": "date", "format": "epoch_millis"}

TRANSACTIONS_INDEX = "transactions"
ACCOUNTS_INDEX = "accounts"
TAXONOMY_INDEX = "taxonomy"
GOALS_INDEX = "goals"

# bge-m3 embedding-dimension — SKAL matche modellen embed-workeren og
# ai-service (query-siden) bruger; drift her degraderer kNN tavst.
EMBEDDING_DIMS = 1024

# Versioner per index; bump ved mapping-ændring → bootstrap reindexer
# gamle fysiske indices og swapper alias (se bootstrap.ensure_indices).
# v2 (transactions, AI-20): description_vector + embedding_event_ts +
# text-subfelter på kategorinavne til hybrid BM25.
INDEX_VERSIONS: dict[str, str] = {
    TRANSACTIONS_INDEX: "v2",
    ACCOUNTS_INDEX: "v1",
    TAXONOMY_INDEX: "v1",
    GOALS_INDEX: "v1",
}

INDEX_DEFINITIONS: dict[str, dict[str, Any]] = {
    TRANSACTIONS_INDEX: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "transaction_id": {"type": "long"},
                "account_id": {"type": "long"},
                "user_id": {"type": "long"},
                "amount": _AMOUNT,
                # Denormaliseret ved skrivning så udgifts-summer ikke
                # kræver painless-scripts på query-tid.
                "amount_abs": _AMOUNT,
                "transaction_type": {"type": "keyword"},
                "tx_date": {"type": "date", "format": "strict_date"},
                "description": {
                    "type": "text",
                    "analyzer": "danish",
                    "fields": {"raw": {"type": "keyword", "ignore_above": 256}},
                },
                "category_id": {"type": "long"},
                # text-subfelter så hybrid-BM25 kan matche kategorinavne
                # ("dagligvarer") uden synonym-hacks på dokument-prosaen.
                "category_name": {
                    "type": "keyword",
                    "fields": {"text": {"type": "text", "analyzer": "danish"}},
                },
                "subcategory_id": {"type": "long"},
                "subcategory_name": {
                    "type": "keyword",
                    "fields": {"text": {"type": "text", "analyzer": "danish"}},
                },
                "categorization_tier": {"type": "keyword"},
                "categorization_confidence": {"type": "keyword"},
                # AI-20: kNN-side af hybrid search. Skrives af
                # embedding-consumeren (aldrig af projektorerne); mangler
                # den, degraderer søgning til BM25-only.
                "description_vector": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMS,
                    "index": True,
                    "similarity": "cosine",
                },
                "is_deleted": {"type": "boolean"},
                "core_event_ts": _TS,
                "categorization_event_ts": _TS,
                "embedding_event_ts": _TS,
                "updated_at": _TS,
            },
        },
    },
    ACCOUNTS_INDEX: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "account_id": {"type": "long"},
                "user_id": {"type": "long"},
                "name": {"type": "keyword"},
                "saldo": _AMOUNT,
                "budget_start_day": {"type": "integer"},
                # Ingen account.deleted-event findes endnu, men feltet
                # holdes konsistent med de øvrige indices — den fælles
                # guard-upsert bruger det som terminal-flag.
                "is_deleted": {"type": "boolean"},
                "event_ts": _TS,
                "updated_at": _TS,
            },
        },
    },
    TAXONOMY_INDEX: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "doc_type": {"type": "keyword"},  # "category" | "subcategory"
                "category_id": {"type": "long"},
                "subcategory_id": {"type": "long"},
                "name": {"type": "keyword"},
                "category_type": {"type": "keyword"},
                "display_order": {"type": "integer"},
                "is_default": {"type": "boolean"},
                "is_deleted": {"type": "boolean"},
                "event_ts": _TS,
                "updated_at": _TS,
            },
        },
    },
    GOALS_INDEX: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "goal_id": {"type": "long"},
                "user_id": {"type": "long"},
                "name": {"type": "keyword"},
                "target_amount": _AMOUNT,
                "current_amount": _AMOUNT,
                "target_date": {"type": "date", "format": "strict_date"},
                "status": {"type": "keyword"},
                "is_deleted": {"type": "boolean"},
                "event_ts": _TS,
                "updated_at": _TS,
            },
        },
    },
}


def physical_index(prefix: str, name: str) -> str:
    return f"{prefix}{name}_{INDEX_VERSIONS[name]}"


def alias_name(prefix: str, name: str) -> str:
    return f"{prefix}{name}"
