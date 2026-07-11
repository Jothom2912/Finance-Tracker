"""Backfill mod respx-stubbede kildeservices + rigtig ES.

Verificerer idempotens (to kørsler → samme counts), navne-opløsning fra
taksonomien og at live events vinder over backfill-state (event_ts=0)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
import respx
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.mappings import alias_name
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from app.config import Settings
from app.tools.backfill import PAGE_SIZE, BackfillRunner
from elasticsearch import AsyncElasticsearch
from httpx import Response

USER_ID = 1

CATEGORIES = [{"id": 10, "name": "Mad & drikke", "type": "expense", "display_order": 1}]
SUBCATEGORIES = [{"id": 101, "name": "Dagligvarer", "category_id": 10, "is_default": True}]
ACCOUNTS = [{"idAccount": 1, "User_idUser": USER_ID, "name": "Lønkonto", "saldo": 5000.0, "budget_start_day": 25}]
TRANSACTIONS = [
    {
        "id": 1,
        "user_id": USER_ID,
        "account_id": 1,
        "account_name": "Lønkonto",
        "category_id": 10,
        "category_name": "Food",  # stale denormaliseret navn — taksonomien skal vinde
        "amount": "200.00",
        "transaction_type": "expense",
        "description": "Netto",
        "date": "2026-06-02",
        "created_at": "2026-06-02T10:00:00Z",
        "subcategory_id": 101,
        "subcategory_name": None,
        "categorization_tier": "rule",
        "categorization_confidence": "high",
    },
    {
        "id": 2,
        "user_id": USER_ID,
        "account_id": 1,
        "account_name": "Lønkonto",
        "category_id": None,
        "category_name": None,
        "amount": "1000.00",
        "transaction_type": "income",
        "description": "Løn",
        "date": "2026-06-01",
        "created_at": "2026-06-01T10:00:00Z",
        "subcategory_id": None,
        "subcategory_name": None,
        "categorization_tier": None,
        "categorization_confidence": None,
    },
]
GOALS = [
    {
        "idGoal": 5,
        "name": "Ferie",
        "target_amount": 10000.0,
        "current_amount": 2500.0,
        "target_date": "2027-06-01",
        "status": "active",
        "effective_status": "active",
        "progress_percent": 25.0,
        "Account_idAccount": 1,
    }
]


def make_settings(index_prefix: str) -> Settings:
    return Settings(
        transaction_service_url="http://transaction-service:8002",
        account_service_url="http://account-service:8003",
        categorization_service_url="http://categorization-service:8005",
        goal_service_url="http://goal-service:8006",
        jwt_secret="test-secret",
        es_index_prefix=index_prefix,
    )


def stub_services(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("http://categorization-service:8005/api/v1/categories/").mock(
        return_value=Response(200, json=CATEGORIES)
    )
    respx_mock.get("http://categorization-service:8005/api/v1/subcategories/").mock(
        return_value=Response(200, json=SUBCATEGORIES)
    )
    respx_mock.get("http://account-service:8003/api/v1/accounts/").mock(return_value=Response(200, json=ACCOUNTS))

    def transactions_page(request: Any) -> Response:
        skip = int(request.url.params.get("skip", 0))
        rows = TRANSACTIONS[skip : skip + PAGE_SIZE]
        return Response(200, json=rows)

    respx_mock.get("http://transaction-service:8002/api/v1/transactions/").mock(side_effect=transactions_page)
    respx_mock.get("http://goal-service:8006/api/v1/goals").mock(return_value=Response(200, json=GOALS))


async def index_counts(es: AsyncElasticsearch, prefix: str) -> dict[str, int]:
    counts = {}
    for name in ("transactions", "accounts", "taxonomy", "goals"):
        alias = alias_name(prefix, name)
        await es.indices.refresh(index=alias)
        counts[name] = (await es.count(index=alias))["count"]
    return counts


@pytest.fixture
def backfill_settings(index_prefix: str) -> Settings:
    return make_settings(index_prefix)


@respx.mock
async def test_backfill_is_idempotent_and_resolves_names_from_taxonomy(
    es: AsyncElasticsearch, index_prefix: str, backfill_settings: Settings, respx_mock: respx.MockRouter
) -> None:
    stub_services(respx_mock)
    runner = BackfillRunner(es, backfill_settings)

    await runner.run([USER_ID])
    first = await index_counts(es, index_prefix)
    assert first == {"transactions": 2, "accounts": 1, "taxonomy": 2, "goals": 1}

    await BackfillRunner(es, backfill_settings).run([USER_ID])
    second = await index_counts(es, index_prefix)
    assert second == first

    doc = await es.get(index=alias_name(index_prefix, "transactions"), id="1")
    source = doc["_source"]
    # Autoritativ taksonomi vinder over det stale denormaliserede navn.
    assert source["category_name"] == "Mad & drikke"
    assert source["subcategory_name"] == "Dagligvarer"
    assert source["amount"] == 200.0

    account = await es.get(index=alias_name(index_prefix, "accounts"), id="1")
    assert account["_source"]["budget_start_day"] == 25

    goal = await es.get(index=alias_name(index_prefix, "goals"), id="5")
    assert goal["_source"]["name"] == "Ferie"


@respx.mock
async def test_live_events_win_over_backfill(
    es: AsyncElasticsearch, index_prefix: str, backfill_settings: Settings, respx_mock: respx.MockRouter
) -> None:
    stub_services(respx_mock)

    # Et live event ankommer FØR backfillen (fx mens den kører).
    live_ts = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    tx_store = EsTransactionProjectionStore(es, index_prefix)
    await ensure_indices(es, index_prefix)
    await tx_store.upsert_core(
        transaction_id=1,
        account_id=1,
        user_id=USER_ID,
        amount=250.0,  # nyere beløb end kildens 200.00
        transaction_type="expense",
        tx_date=date(2026, 6, 2),
        description="Netto (rettet)",
        category_id=10,
        category_name="Mad & drikke",
        subcategory_id=101,
        subcategory_name="Dagligvarer",
        categorization_tier="manual",
        categorization_confidence=None,
        event_ts=live_ts,
    )

    await BackfillRunner(es, backfill_settings).run([USER_ID])

    doc = await es.get(index=alias_name(index_prefix, "transactions"), id="1")
    source = doc["_source"]
    assert source["amount"] == 250.0  # backfill (event_ts=0) må ikke overskrive
    assert source["description"] == "Netto (rettet)"


@respx.mock
async def test_terminates_when_source_ignores_pagination(
    es: AsyncElasticsearch, index_prefix: str, backfill_settings: Settings, respx_mock: respx.MockRouter
) -> None:
    """transaction-services find_by_account ignorerer skip/limit og
    returnerer alt for kontoen på hver side — backfillen skal stoppe på
    første gentagne side i stedet for at loope uendeligt (observeret i
    compose-stakken ved 216k+ requests)."""
    stub_services(respx_mock)
    # Overstyr transaktions-stubben: ignorér skip helt og returnér en
    # FULD side hver gang (ellers stopper kort-side-betingelsen loopet
    # før guarden overhovedet er i spil).
    full_page = [{**TRANSACTIONS[1], "id": 100 + i, "description": f"Række {i}"} for i in range(PAGE_SIZE)]
    respx_mock.get("http://transaction-service:8002/api/v1/transactions/").mock(
        return_value=Response(200, json=full_page)
    )

    await BackfillRunner(es, backfill_settings).run([USER_ID])

    counts = await index_counts(es, index_prefix)
    assert counts["transactions"] == PAGE_SIZE
