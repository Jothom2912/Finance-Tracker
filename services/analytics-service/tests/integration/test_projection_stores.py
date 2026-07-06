"""Idempotens- og ordering-semantik for projection stores mod rigtig ES.

Kernen i ADR-004's "ingen processed_events-tabel"-beslutning: replays og
out-of-order events skal konvergere via _id-upserts + timestamp-guards.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.mappings import alias_name
from app.adapters.outbound.elasticsearch.taxonomy_store import EsTaxonomyProjectionStore
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from app.application.projections import (
    TaxonomyProjector,
    TransactionProjector,
    event_ts_millis,
)
from contracts.events.category import CategoryCreatedEvent, CategoryUpdatedEvent
from contracts.events.transaction import (
    TransactionCategorizedEvent,
    TransactionCreatedEvent,
    TransactionDeletedEvent,
)
from elasticsearch import AsyncElasticsearch

T0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 6, 1, 12, 0, 1, tzinfo=timezone.utc)
T2 = datetime(2026, 6, 1, 12, 0, 2, tzinfo=timezone.utc)


def created_event(ts: datetime, **overrides: Any) -> TransactionCreatedEvent:
    defaults: dict[str, Any] = {
        "transaction_id": 1,
        "account_id": 10,
        "user_id": 7,
        "amount": "125.50",
        "transaction_type": "expense",
        "tx_date": date(2026, 5, 20),
        "category_id": 3,
        "category": "Dagligvarer",
        "description": "NETTO 1234",
        "timestamp": ts,
    }
    defaults.update(overrides)
    return TransactionCreatedEvent(**defaults)


def categorized_event(ts: datetime, **overrides: Any) -> TransactionCategorizedEvent:
    defaults: dict[str, Any] = {
        "transaction_id": 1,
        "category_id": 5,
        "category_name": "Transport",
        "subcategory_id": 12,
        "subcategory_name": "Brændstof",
        "tier": "rule",
        "confidence": "high",
        "timestamp": ts,
    }
    defaults.update(overrides)
    return TransactionCategorizedEvent(**defaults)


@pytest.fixture
async def stores(
    es: AsyncElasticsearch, index_prefix: str
) -> tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str]:
    await ensure_indices(es, index_prefix)
    tx_alias = alias_name(index_prefix, "transactions")
    return (
        EsTransactionProjectionStore(es, index_prefix),
        EsTaxonomyProjectionStore(es, index_prefix),
        tx_alias,
    )


async def get_tx_doc(es: AsyncElasticsearch, alias: str, tx_id: int = 1) -> dict[str, Any]:
    doc = await es.get(index=alias, id=str(tx_id))
    return dict(doc["_source"])


class TestTransactionProjectionIdempotency:
    async def test_same_created_event_twice_converges(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
    ) -> None:
        tx_store, taxonomy_store, alias = stores
        projector = TransactionProjector(tx_store, taxonomy_store)
        event = created_event(T0)

        await projector.handle_created_or_updated(event)
        first = await get_tx_doc(es, alias)
        await projector.handle_created_or_updated(event)
        second = await get_tx_doc(es, alias)

        assert first == second
        assert second["amount"] == 125.50
        assert second["amount_abs"] == 125.50
        assert second["category_name"] == "Dagligvarer"
        assert second["is_deleted"] is False

    async def test_categorized_before_created_merges_both_field_groups(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
    ) -> None:
        tx_store, taxonomy_store, alias = stores
        projector = TransactionProjector(tx_store, taxonomy_store)

        await projector.handle_categorized(categorized_event(T1))
        # Partielt dokument: usynligt for queries (ingen account_id endnu).
        partial = await get_tx_doc(es, alias)
        assert "account_id" not in partial
        assert partial["category_name"] == "Transport"

        await projector.handle_created_or_updated(created_event(T0))
        doc = await get_tx_doc(es, alias)

        assert doc["account_id"] == 10
        assert doc["tx_date"] == "2026-05-20"
        # created-eventet (T0) er ældre end kategoriseringen (T1) og må
        # ikke clobre den.
        assert doc["category_id"] == 5
        assert doc["category_name"] == "Transport"
        assert doc["subcategory_name"] == "Brændstof"
        assert doc["categorization_tier"] == "rule"

    async def test_stale_core_event_does_not_roll_back_newer_core_state(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
    ) -> None:
        tx_store, taxonomy_store, alias = stores
        projector = TransactionProjector(tx_store, taxonomy_store)

        await projector.handle_created_or_updated(created_event(T2, amount="200.00"))
        await projector.handle_created_or_updated(created_event(T0, amount="125.50"))

        doc = await get_tx_doc(es, alias)
        assert doc["amount"] == 200.00

    async def test_delete_is_terminal_against_late_replay(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
    ) -> None:
        tx_store, taxonomy_store, alias = stores
        projector = TransactionProjector(tx_store, taxonomy_store)

        await projector.handle_created_or_updated(created_event(T0))
        await projector.handle_deleted(
            TransactionDeletedEvent(transaction_id=1, account_id=10, user_id=7, amount="125.50", timestamp=T1)
        )
        # Sen replay af created (endda med nyere timestamp end delete).
        await projector.handle_created_or_updated(created_event(T2))

        doc = await get_tx_doc(es, alias)
        assert doc["is_deleted"] is True

    async def test_core_event_resolves_subcategory_name_from_taxonomy(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
    ) -> None:
        tx_store, taxonomy_store, alias = stores
        await taxonomy_store.upsert_subcategory(
            subcategory_id=12,
            category_id=3,
            name="Brændstof",
            is_default=False,
            is_deleted=False,
            event_ts=event_ts_millis(created_event(T0)),
        )
        projector = TransactionProjector(tx_store, taxonomy_store)

        await projector.handle_created_or_updated(created_event(T1, subcategory_id=12))

        doc = await get_tx_doc(es, alias)
        assert doc["subcategory_name"] == "Brændstof"


class TestTaxonomyRenamePropagation:
    async def test_category_rename_propagates_to_transaction_docs(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
    ) -> None:
        tx_store, taxonomy_store, alias = stores
        tx_projector = TransactionProjector(tx_store, taxonomy_store)
        taxonomy_projector = TaxonomyProjector(taxonomy_store)

        await tx_projector.handle_created_or_updated(created_event(T0))
        await taxonomy_projector.handle_category(
            CategoryUpdatedEvent(category_id=3, name="Mad & dagligvarer", category_type="expense", timestamp=T1)
        )

        await es.indices.refresh(index=alias)
        doc = await get_tx_doc(es, alias)
        assert doc["category_name"] == "Mad & dagligvarer"

    async def test_stale_category_event_does_not_propagate_old_name(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
    ) -> None:
        tx_store, taxonomy_store, alias = stores
        tx_projector = TransactionProjector(tx_store, taxonomy_store)
        taxonomy_projector = TaxonomyProjector(taxonomy_store)

        await tx_projector.handle_created_or_updated(created_event(T0))
        await taxonomy_projector.handle_category(
            CategoryUpdatedEvent(category_id=3, name="Mad & dagligvarer", category_type="expense", timestamp=T2)
        )
        # Stale rename (ældre timestamp) må hverken opdatere taxonomy-doc
        # eller transaktionernes denormaliserede navn.
        await taxonomy_projector.handle_category(
            CategoryUpdatedEvent(category_id=3, name="Gammelt navn", category_type="expense", timestamp=T0)
        )

        await es.indices.refresh(index=alias)
        doc = await get_tx_doc(es, alias)
        assert doc["category_name"] == "Mad & dagligvarer"

    async def test_category_created_upserts_taxonomy_doc(
        self,
        es: AsyncElasticsearch,
        stores: tuple[EsTransactionProjectionStore, EsTaxonomyProjectionStore, str],
        index_prefix: str,
    ) -> None:
        _, taxonomy_store, _ = stores
        projector = TaxonomyProjector(taxonomy_store)
        await projector.handle_category(
            CategoryCreatedEvent(category_id=3, name="Dagligvarer", category_type="expense", timestamp=T0)
        )

        doc = await es.get(index=alias_name(index_prefix, "taxonomy"), id="category:3")
        assert doc["_source"]["name"] == "Dagligvarer"
        assert doc["_source"]["doc_type"] == "category"
