"""EsSearch (AI-20): filter-oversættelse, degradering og response-mapping.

HTTP pinnes ved httpx-seamet (respx ikke i dev-deps → monkeypatch af
httpx.post) — testene fryser kontrakten mod analytics-services
hybrid-endpoint, så drift opdages her og ikke i chatten.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from app.adapters.outbound.es_search import EsSearch

HYBRID_RESPONSE = {
    "items": [
        {
            "id": 3,
            "amount": -300.0,
            "description": "Netto butik",
            "date": "2026-06-05",
            "type": "expense",
            "category_id": 10,
            "category_name": "Dagligvarer",
            "account_id": 2,
        },
        {
            "id": 4,
            "amount": -50.0,
            "description": None,
            "date": "2026-06-06",
            "type": "expense",
            "category_id": None,
            "category_name": None,
            "account_id": 1,
        },
    ],
    "used_knn": True,
}


class FakeHttp:
    """Opsamler httpx.post-kald; skelner Ollama-embed fra analytics-søgning."""

    def __init__(self, embed_fails: bool = False) -> None:
        self.embed_fails = embed_fails
        self.search_request: dict[str, Any] | None = None
        self.search_headers: dict[str, str] | None = None

    def post(self, url: str, *, json: dict[str, Any], headers: dict[str, str] | None = None, timeout: float) -> Any:
        if "/api/embed" in url:
            if self.embed_fails:
                raise httpx.ConnectError("ollama nede")
            return httpx.Response(200, json={"embeddings": [[0.1] * 4]}, request=httpx.Request("POST", url))
        self.search_request = json
        self.search_headers = headers
        return httpx.Response(200, json=HYBRID_RESPONSE, request=httpx.Request("POST", url))


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    fake = FakeHttp()
    monkeypatch.setattr("app.adapters.outbound.es_search.httpx.post", fake.post)
    return fake


def test_sends_query_vector_and_jwt(fake_http: FakeHttp) -> None:
    search = EsSearch(user_id=9001, token="jwt-token")

    items, elapsed_ms = search.search("netto", top_k=5)

    assert fake_http.search_request is not None
    assert fake_http.search_request["query"] == "netto"
    assert fake_http.search_request["query_vector"] == [0.1] * 4
    assert fake_http.search_request["limit"] == 5
    assert fake_http.search_headers == {"Authorization": "Bearer jwt-token"}
    assert elapsed_ms >= 0


def test_period_and_filters_translate_to_endpoint_params(fake_http: FakeHttp) -> None:
    search = EsSearch(user_id=9001, token="t")

    search.search(
        "udgifter",
        period="2026-02",
        filters={
            "category": "Dagligvarer",
            "amount": {"$gte": 500.0, "$lte": 900.0},
            "is_expense": True,
        },
    )

    req = fake_http.search_request
    assert req is not None
    assert req["start_date"] == "2026-02-01"
    assert req["end_date"] == "2026-02-28"  # ikke-skudår
    assert req["category_name"] == "Dagligvarer"
    assert req["amount_min"] == 500.0
    assert req["amount_max"] == 900.0
    assert req["tx_type"] == "expense"


def test_mismatched_user_id_filter_is_a_dispatcher_bug(fake_http: FakeHttp) -> None:
    search = EsSearch(user_id=9001, token="t")

    with pytest.raises(ValueError, match="auto-injected"):
        search.search("netto", filters={"user_id": 9002})


def test_embed_failure_degrades_to_bm25_only(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHttp(embed_fails=True)
    monkeypatch.setattr("app.adapters.outbound.es_search.httpx.post", fake.post)
    search = EsSearch(user_id=9001, token="t")

    items, _ = search.search("netto")

    assert fake.search_request is not None
    assert "query_vector" not in fake.search_request
    assert len(items) == 2


def test_response_maps_to_transaction_items_with_fallbacks(fake_http: FakeHttp) -> None:
    search = EsSearch(user_id=9001, token="t")

    items, _ = search.search("netto")

    assert [i.id for i in items] == [3, 4]
    assert items[0].category == "Dagligvarer"
    assert items[0].amount == -300.0
    assert items[0].date == "2026-06-05"
    # Manglende felter må aldrig crashe — fallback-labels.
    assert items[1].category == "Ukategoriseret"
    assert items[1].description == ""


def test_build_search_returns_es_adapter() -> None:
    from app.application.pipeline import build_search

    assert isinstance(build_search(user_id=1, token="t"), EsSearch)
