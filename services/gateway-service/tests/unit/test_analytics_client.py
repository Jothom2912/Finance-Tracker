"""JSON→DTO-mapping og fejl-oversættelse i analytics-service-klienten."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from app.adapters.outbound.analytics_client import (
    AnalyticsServiceUnavailable,
    HttpFinancialAnalyticsRepository,
)

OVERVIEW_JSON = {
    "start_date": "2026-06-01",
    "end_date": "2026-06-30",
    "total_income": 1000.0,
    "total_expenses": 375.0,
    "net_change_in_period": 625.0,
    "expenses_by_category": [
        {
            "category_id": 10,
            "category_name": "Mad & drikke",
            "amount": 325.0,
            "subcategories": [{"subcategory_id": 101, "subcategory_name": "Dagligvarer", "amount": 200.0}],
        }
    ],
    "current_account_balance": 625.0,
    "average_monthly_expenses": 375.0,
}


def make_repo(handler) -> HttpFinancialAnalyticsRepository:
    return HttpFinancialAnalyticsRepository("Bearer token", transport=httpx.MockTransport(handler))


def test_overview_maps_json_to_dto_and_forwards_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=OVERVIEW_JSON)

    overview = make_repo(handler).get_financial_overview(1, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30))

    assert seen["auth"] == "Bearer token"
    assert seen["params"] == {
        "account_id": "1",
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
    }
    assert overview.total_expenses == 375.0
    assert overview.expenses_by_category[0].subcategories[0].subcategory_name == "Dagligvarer"


def test_expenses_by_month_maps_list(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["budget_start_day"] == "15"
        return httpx.Response(200, json=[{"month": "2026-06", "total_expenses": 375.0}])

    result = make_repo(handler).get_expenses_by_month(1, budget_start_day=15)
    assert [(m.month, m.total_expenses) for m in result] == [("2026-06", 375.0)]


def test_transactions_unwraps_items_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "id": 2,
                        "amount": 200.0,
                        "description": "Groceries",
                        "date": "2026-06-02",
                        "type": "expense",
                        "category_id": 10,
                        "category_name": "Mad & drikke",
                        "subcategory_id": 101,
                        "subcategory_name": "Dagligvarer",
                        "account_id": 1,
                        "categorization_tier": "rule",
                    }
                ],
            },
        )

    result = make_repo(handler).list_transactions(1, limit=10)
    assert len(result) == 1
    assert result[0].id == 2
    assert result[0].date == date(2026, 6, 2)


def test_transport_error_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nede")

    with pytest.raises(AnalyticsServiceUnavailable):
        make_repo(handler).get_financial_overview(1)


def test_503_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "Read-store nede"})

    with pytest.raises(AnalyticsServiceUnavailable):
        make_repo(handler).get_financial_overview(1)


def test_other_http_errors_propagate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "ugyldig periode"})

    with pytest.raises(httpx.HTTPStatusError):
        make_repo(handler).get_financial_overview(1)
