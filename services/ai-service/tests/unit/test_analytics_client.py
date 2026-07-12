"""Unit tests for AnalyticsClient — AI-19: largest_expense/category_breakdown
served by analytics-service (ES read-store), budget_status by budget-service.

HTTP is stubbed at the `_get_json` seam so the tests pin the request contract
(endpoint, params) and the response→domain mapping, not httpx plumbing.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.adapters.outbound.analytics_client import AnalyticsClient, _period_to_date_range
from app.config import settings


@pytest.fixture()
def client() -> AnalyticsClient:
    return AnalyticsClient(token="test-token", account_id=7)


def _tx(id: int, amount: float, category: str | None = "Dagligvarer", description: str = "Netto") -> dict[str, Any]:
    return {
        "id": id,
        "amount": amount,
        "description": description,
        "date": "2026-04-15",
        "type": "expense",
        "category_id": 3,
        "category_name": category,
        "account_id": 7,
    }


class TestLargestExpenses:
    async def test_queries_analytics_transactions_with_server_side_sort(
        self, client: AnalyticsClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        get_json = AsyncMock(return_value={"total_count": 2, "items": [_tx(1, -412.0), _tx(2, -287.5)]})
        monkeypatch.setattr(client, "_get_json", get_json)

        items, elapsed = await client.get_largest_expenses("2026-04")

        base_url, path, params = get_json.call_args.args[:3]
        assert base_url == settings.ANALYTICS_SERVICE_URL
        assert path == "/api/v1/analytics/transactions"
        assert params["account_id"] == 7
        assert params["tx_type"] == "expense"
        assert params["sort"] == "amount_desc"
        assert params["limit"] == 5
        assert params["start_date"] == "2026-04-01"
        assert params["end_date"] == "2026-04-30"
        assert [i.id for i in items] == [1, 2]
        assert items[0].amount == 412.0  # abs af negativt beløb
        assert elapsed >= 0

    async def test_category_filter_is_client_side_name_match_until_ai21(
        self, client: AnalyticsClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        get_json = AsyncMock(
            return_value={
                "total_count": 3,
                "items": [
                    _tx(1, -900.0, category="Bolig", description="Husleje"),
                    _tx(2, -412.0, category="Dagligvarer"),
                    _tx(3, -287.5, category="Dagligvarer"),
                ],
            }
        )
        monkeypatch.setattr(client, "_get_json", get_json)

        items, _ = await client.get_largest_expenses("2026-04", category="dagligvarer")

        # Kategorifilter → større side hentes, matches case-insensitivt på navn
        assert get_json.call_args.args[2]["limit"] == 200
        assert [i.id for i in items] == [2, 3]

    async def test_missing_category_name_maps_to_ukategoriseret(
        self, client: AnalyticsClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        get_json = AsyncMock(return_value={"total_count": 1, "items": [_tx(1, -50.0, category=None)]})
        monkeypatch.setattr(client, "_get_json", get_json)

        items, _ = await client.get_largest_expenses("2026-04")

        assert items[0].category == "Ukategoriseret"


class TestCategoryBreakdown:
    async def test_queries_analytics_overview_and_computes_percentages(
        self, client: AnalyticsClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        get_json = AsyncMock(
            return_value={
                "total_expenses": 1000.0,
                "expenses_by_category": [
                    {"category_id": 3, "category_name": "Dagligvarer", "amount": 750.0, "subcategories": []},
                    {"category_id": 5, "category_name": "Transport", "amount": 250.0, "subcategories": []},
                ],
            }
        )
        monkeypatch.setattr(client, "_get_json", get_json)

        items, _ = await client.get_category_breakdown("2026-04")

        base_url, path, params = get_json.call_args.args[:3]
        assert base_url == settings.ANALYTICS_SERVICE_URL
        assert path == "/api/v1/analytics/overview"
        assert params == {"account_id": 7, "start_date": "2026-04-01", "end_date": "2026-04-30"}
        assert [(i.category, i.amount, i.percentage) for i in items] == [
            ("Dagligvarer", 750.0, 75.0),
            ("Transport", 250.0, 25.0),
        ]

    async def test_empty_breakdown_returns_empty_list(
        self, client: AnalyticsClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        get_json = AsyncMock(return_value={"expenses_by_category": []})
        monkeypatch.setattr(client, "_get_json", get_json)

        items, _ = await client.get_category_breakdown("2026-04")

        assert items == []


class TestBudgetStatus:
    async def test_still_queries_budget_service_with_account_header(
        self, client: AnalyticsClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        get_json = AsyncMock(
            return_value={
                "items": [
                    {
                        "category_name": "Dagligvarer",
                        "budget_amount": "3000",
                        "spent_amount": "2500",
                        "remaining_amount": "500",
                        "percentage_used": "83.3",
                    }
                ],
                "total_budget": 3000,
                "total_spent": 2500,
                "total_remaining": 500,
                "over_budget_count": 0,
            }
        )
        monkeypatch.setattr(client, "_get_json", get_json)

        payload, _ = await client.get_budget_status("2026-03")

        base_url, path, params = get_json.call_args.args[:3]
        assert base_url == settings.BUDGET_SERVICE_URL
        assert path == "/api/v1/monthly-budgets/summary"
        assert params == {"month": 3, "year": 2026}
        # Budget-service kræver X-Account-ID-headeren
        assert get_json.call_args.kwargs["headers"]["X-Account-ID"] == "7"
        assert payload.items[0].budget_amount == 3000.0


def test_period_to_date_range_handles_leap_february() -> None:
    assert _period_to_date_range("2024-02") == ("2024-02-01", "2024-02-29")
