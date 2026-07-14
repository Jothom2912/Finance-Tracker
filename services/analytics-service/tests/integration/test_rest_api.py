"""REST-laget mod rigtig ES: auth, happy path og domain-fejl-mapping."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.mappings import alias_name
from app.adapters.outbound.elasticsearch.transaction_store import (
    EsTransactionProjectionStore,
)
from app.config import settings
from app.main import app
from elasticsearch import AsyncElasticsearch

from tests.integration.test_query_store import GOLDEN_ROWS, USER_ID, seed_transactions

TEST_SECRET = "test-secret"


def auth_header(user_id: int = USER_ID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(
    es: AsyncElasticsearch, index_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    # Lifespan køres ikke af ASGITransport — state og settings sættes
    # direkte, med test-prefix så hver test får friske indices.
    monkeypatch.setattr(settings, "jwt_secret", TEST_SECRET)
    monkeypatch.setattr(settings, "es_index_prefix", index_prefix)
    await ensure_indices(es, index_prefix)
    await seed_transactions(EsTransactionProjectionStore(es, index_prefix), GOLDEN_ROWS)
    await es.indices.refresh(index=alias_name(index_prefix, "transactions"))
    app.state.es = es

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://analytics") as c:
        yield c


async def test_requires_bearer_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/analytics/overview", params={"account_id": 1})
    assert response.status_code == 401


async def test_overview_happy_path(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/analytics/overview",
        params={"account_id": 1, "start_date": "2026-06-01", "end_date": "2026-06-30"},
        headers=auth_header(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_income"] == 1000
    assert body["total_expenses"] == 375
    assert body["current_account_balance"] == 625
    assert {c["category_name"] for c in body["expenses_by_category"]} == {
        "Food",
        "Ukategoriseret",
    }


async def test_invalid_period_maps_to_400(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/analytics/overview",
        params={"account_id": 1, "start_date": "2026-07-01", "end_date": "2026-06-01"},
        headers=auth_header(),
    )
    assert response.status_code == 400
    assert "Startdato" in response.json()["detail"]


async def test_foreign_user_sees_empty_data_not_errors(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/analytics/overview",
        params={"account_id": 1, "start_date": "2026-06-01", "end_date": "2026-06-30"},
        headers=auth_header(user_id=999),
    )
    assert response.status_code == 200
    assert response.json()["total_expenses"] == 0


async def test_transactions_search_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/analytics/transactions",
        params={"account_id": 1, "search": "groceries"},
        headers=auth_header(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 1
    assert body["items"][0]["description"] == "Groceries"


async def test_hybrid_search_bm25_only_happy_path(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analytics/search/hybrid",
        json={"query": "groceries"},
        headers=auth_header(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["used_knn"] is False
    assert [i["description"] for i in body["items"]] == ["Groceries"]


async def test_hybrid_search_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/analytics/search/hybrid", json={"query": "groceries"})
    assert response.status_code == 401


async def test_hybrid_search_rejects_wrong_vector_dims(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/analytics/search/hybrid",
        json={"query": "groceries", "query_vector": [0.1, 0.2, 0.3]},
        headers=auth_header(),
    )
    assert response.status_code == 422
    assert "1024" in response.text


async def test_read_store_unavailable_maps_to_503(index_prefix: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", TEST_SECRET)
    monkeypatch.setattr(settings, "es_index_prefix", index_prefix)
    # Peg state på et dødt ES-endpoint — domain-fejlen skal blive 503.
    dead_es = AsyncElasticsearch("http://127.0.0.1:9", request_timeout=1, max_retries=0)
    app.state.es = dead_es
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://analytics") as c:
            response = await c.get(
                "/api/v1/analytics/overview",
                params={"account_id": 1},
                headers=auth_header(),
            )
        assert response.status_code == 503
    finally:
        await dead_es.close()
