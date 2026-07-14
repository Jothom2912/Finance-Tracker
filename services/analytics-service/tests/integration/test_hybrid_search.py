"""AI-20 hybrid search mod rigtig ES: BM25+kNN, RRF, filtre, degradering.

Vektorer i testene er one-hot/kombinationer så cosine-rangeringen er
deterministisk og læselig: ``vec(0)`` er ortogonal på ``vec(1)`` osv.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.mappings import EMBEDDING_DIMS, alias_name
from app.adapters.outbound.elasticsearch.query_store import EsAnalyticsQueryStore
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from elasticsearch import AsyncElasticsearch

TS = int(datetime(2026, 6, 10, tzinfo=timezone.utc).timestamp() * 1000)
USER_ID = 7
OTHER_USER_ID = 8


def vec(direction: int, weight: float = 1.0, mix: tuple[int, float] | None = None) -> list[float]:
    v = [0.0] * EMBEDDING_DIMS
    v[direction] = weight
    if mix is not None:
        v[mix[0]] = mix[1]
    return v


ROWS: list[dict[str, Any]] = [
    # id, beskrivelse, kategori, beløb, konto, vektor
    {
        "transaction_id": 1,
        "description": "Netto",
        "category_id": 10,
        "category_name": "Dagligvarer",
        "amount": -100.0,
        "account_id": 1,
        "vector": vec(1),  # ortogonal på query-vektoren e0
    },
    {
        "transaction_id": 2,
        "description": "Fitness World",
        "category_id": 20,
        "category_name": "Sundhed",
        "amount": -249.0,
        "account_id": 1,
        "vector": vec(0),  # kNN-favorit for query e0
    },
    {
        "transaction_id": 3,
        "description": "Netto butik",
        "category_id": 10,
        "category_name": "Dagligvarer",
        "amount": -300.0,
        "account_id": 2,
        "vector": vec(0, 0.9, mix=(1, 0.4)),  # næsten-parallel med e0
    },
    {
        "transaction_id": 4,
        "description": "Apoteket",
        "category_id": 20,
        "category_name": "Sundhed",
        "amount": -50.0,
        "account_id": 1,
        "vector": None,  # ingen embedding endnu (Ollama-lag/DLQ)
    },
    # Fillers: semantisk mellemtætte på e0, intet leksikalsk "netto"-
    # match. kNN's top-k returnerer ALLE docs (også ortogonale, cos=0),
    # så uden fillers ville doc 1 stå på kNN-rank 3 og RRF-matematikken
    # (1/61 + 1/63 > 2/62) marginalt favorisere rank1+rank3 over
    # rank2+rank2. Fillers skubber ikke-matches ned, som et rigtigt
    # korpus gør.
    {
        "transaction_id": 5,
        "description": "Bilka",
        "category_id": 30,
        "category_name": "Andet",
        "amount": -60.0,
        "account_id": 1,
        "vector": vec(0, 0.6, mix=(2, 0.8)),  # cos ≈ 0.6 mod e0
    },
    {
        "transaction_id": 6,
        "description": "Rema 1000",
        "category_id": 30,
        "category_name": "Andet",
        "amount": -70.0,
        "account_id": 1,
        "vector": vec(0, 0.5, mix=(3, 0.87)),  # cos ≈ 0.5 mod e0
    },
]


@pytest.fixture
async def query_store(es: AsyncElasticsearch, index_prefix: str) -> EsAnalyticsQueryStore:
    await ensure_indices(es, index_prefix)
    store = EsTransactionProjectionStore(es, index_prefix)
    for row in ROWS:
        await store.upsert_core(
            transaction_id=row["transaction_id"],
            account_id=row["account_id"],
            user_id=USER_ID,
            amount=row["amount"],
            transaction_type="expense",
            tx_date=date(2026, 6, 5),
            description=row["description"],
            category_id=row["category_id"],
            category_name=row["category_name"],
            subcategory_id=None,
            subcategory_name=None,
            categorization_tier=None,
            categorization_confidence=None,
            event_ts=TS,
        )
        if row["vector"] is not None:
            await store.update_embedding(
                transaction_id=row["transaction_id"],
                vector=row["vector"],
                event_ts=TS,
            )
    # Fremmed brugers doc: perfekt vektor-match — må ALDRIG dukke op.
    await store.upsert_core(
        transaction_id=900,
        account_id=9,
        user_id=OTHER_USER_ID,
        amount=-100.0,
        transaction_type="expense",
        tx_date=date(2026, 6, 5),
        description="Netto",
        category_id=10,
        category_name="Dagligvarer",
        subcategory_id=None,
        subcategory_name=None,
        categorization_tier=None,
        categorization_confidence=None,
        event_ts=TS,
    )
    await store.update_embedding(transaction_id=900, vector=vec(0), event_ts=TS)
    await es.indices.refresh(index=alias_name(index_prefix, "transactions"))
    return EsAnalyticsQueryStore(es, index_prefix)


class TestBm25Only:
    async def test_no_vector_degrades_to_bm25(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.hybrid_search_transactions(user_id=USER_ID, query="netto")

        assert result.used_knn is False
        assert {i.id for i in result.items} == {1, 3}

    async def test_category_name_matches_via_danish_text_subfield(self, query_store: EsAnalyticsQueryStore) -> None:
        # "dagligvarer" står IKKE i nogen beskrivelse — kun i kategorinavnet.
        result = await query_store.hybrid_search_transactions(user_id=USER_ID, query="dagligvarer")

        assert {i.id for i in result.items} == {1, 3}

    async def test_doc_without_vector_is_still_searchable(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.hybrid_search_transactions(user_id=USER_ID, query="apoteket")

        assert [i.id for i in result.items] == [4]


class TestHybridRrf:
    async def test_consensus_doc_outranks_single_list_winners(self, query_store: EsAnalyticsQueryStore) -> None:
        # Doc 3 er i BEGGE lister (BM25: "netto", kNN: ~e0); doc 1 er
        # BM25-only, doc 2 er kNN-only. RRF skal sætte 3 øverst.
        result = await query_store.hybrid_search_transactions(user_id=USER_ID, query="netto", query_vector=vec(0))

        assert result.used_knn is True
        assert result.items[0].id == 3
        assert {i.id for i in result.items} >= {1, 2, 3}

    async def test_semantic_match_found_without_lexical_overlap(self, query_store: EsAnalyticsQueryStore) -> None:
        # Query-tekst uden leksikalsk match — kNN-benet skal bære.
        result = await query_store.hybrid_search_transactions(
            user_id=USER_ID, query="motion træningscenter", query_vector=vec(0)
        )

        assert 2 in {i.id for i in result.items}


class TestFilters:
    async def test_tenant_isolation_beats_perfect_vector_match(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.hybrid_search_transactions(
            user_id=USER_ID, query="netto", query_vector=vec(0), limit=50
        )

        assert 900 not in {i.id for i in result.items}

    async def test_account_filter_is_optional_and_effective(self, query_store: EsAnalyticsQueryStore) -> None:
        across = await query_store.hybrid_search_transactions(user_id=USER_ID, query="netto")
        assert {i.id for i in across.items} == {1, 3}

        scoped = await query_store.hybrid_search_transactions(user_id=USER_ID, query="netto", account_id=1)
        assert {i.id for i in scoped.items} == {1}

    async def test_amount_range_filters_both_legs(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.hybrid_search_transactions(
            user_id=USER_ID,
            query="netto",
            query_vector=vec(0),
            amount_min=200.0,
        )

        # amount_abs ≥ 200 fjerner doc 1 (100 kr) fra BM25-benet, men
        # beholder doc 3 (300 kr) og kNN-benets doc 2 (249 kr).
        assert {i.id for i in result.items} == {2, 3}

    async def test_category_id_filter(self, query_store: EsAnalyticsQueryStore) -> None:
        result = await query_store.hybrid_search_transactions(
            user_id=USER_ID, query="netto", query_vector=vec(0), category_id=10
        )

        assert {i.id for i in result.items} == {1, 3}
