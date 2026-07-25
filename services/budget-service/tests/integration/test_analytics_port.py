"""Tests for AnalyticsSpendPort — forbrugs-adapteren mod analytics-service (P1-13).

Payloadet i ``JUNE_PAYLOAD`` er formen af et rigtigt svar, målt mod den
kørende analytics-service for konto 1 / juni 2026 inden adapteren blev
skrevet. Tallene summer til 16 739,83 — præcis det forbrug den gamle
``TransactionPort`` rapporterede som 5 180,32, fordi den kun så de 50
nyeste rækker.

Bruger respx; kræver ikke Docker.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import Response

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dummy/dummy")
os.environ.setdefault("JWT_SECRET", "test-secret")

OVERVIEW_URL = "http://localhost:8006/api/v1/analytics/overview"

JUNE_PAYLOAD = {
    "start_date": "2026-06-01",
    "end_date": "2026-06-30",
    "total_income": 12848.0,
    "total_expenses": 16739.83,
    "net_change_in_period": -3891.83,
    "expenses_by_category": [
        {"category_id": 2, "category_name": "Bolig", "amount": 5560.0},
        {"category_id": 1, "category_name": "Mad & drikke", "amount": 3629.73},
        {"category_id": 8, "category_name": "Diverse", "amount": 2368.45},
        {"category_id": 9, "category_name": "Indkomst", "amount": 1500.0},
        {"category_id": 10, "category_name": "Overfoersler", "amount": 1428.0},
        {"category_id": 5, "category_name": "Personlig", "amount": 891.75},
        {"category_id": 4, "category_name": "Underholdning & fritid", "amount": 712.0},
        {"category_id": 3, "category_name": "Transport", "amount": 649.9},
    ],
}

JUNE_START = date(2026, 6, 1)
JUNE_END = date(2026, 6, 30)


@pytest.fixture()
def port():
    from app.adapters.outbound.analytics_port import AnalyticsSpendPort

    return AnalyticsSpendPort()


class TestExpensesByCategory:
    @respx.mock
    async def test_maps_buckets_to_category_id_keyed_dict(self, port) -> None:
        respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=JUNE_PAYLOAD))

        result = await port.get_expenses_by_category(1, JUNE_START, JUNE_END, user_id=1)

        assert result[2] == 5560.0
        assert result[1] == 3629.73
        assert result[3] == 649.9
        assert len(result) == 8

    @respx.mock
    async def test_uncategorised_bucket_is_excluded(self, port) -> None:
        """Ukategoriseret har ingen budgetlinje at hænge på — den hører i totalen."""
        payload = {
            **JUNE_PAYLOAD,
            "expenses_by_category": [
                {"category_id": 1, "category_name": "Mad & drikke", "amount": 100.0},
                {"category_id": None, "category_name": "Ukategoriseret", "amount": 250.0},
            ],
        }
        respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=payload))

        result = await port.get_expenses_by_category(1, JUNE_START, JUNE_END, user_id=1)

        assert result == {1: 100.0}

    @respx.mock
    async def test_empty_period_gives_empty_dict(self, port) -> None:
        payload = {**JUNE_PAYLOAD, "total_expenses": 0.0, "expenses_by_category": []}
        respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=payload))

        assert await port.get_expenses_by_category(1, JUNE_START, JUNE_END, user_id=1) == {}


class TestTotalExpenses:
    @respx.mock
    async def test_returns_total_as_decimal(self, port) -> None:
        respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=JUNE_PAYLOAD))

        result = await port.get_total_expenses(1, JUNE_START, JUNE_END, user_id=1)

        assert result == Decimal("16739.83")
        assert isinstance(result, Decimal)

    @respx.mock
    async def test_total_includes_uncategorised_unlike_per_category(self, port) -> None:
        """Kernen i beslutningen: totalen er IKKE summen af de kategoriserede buckets.

        Bruger get_total_expenses frem for at summere buckets — ellers ville
        ukategoriseret forbrug oppuste månedens overskud, som det gjorde før P1-13.
        """
        payload = {
            **JUNE_PAYLOAD,
            "total_expenses": 350.0,
            "expenses_by_category": [
                {"category_id": 1, "category_name": "Mad & drikke", "amount": 100.0},
                {"category_id": None, "category_name": "Ukategoriseret", "amount": 250.0},
            ],
        }
        respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=payload))

        per_category = await port.get_expenses_by_category(1, JUNE_START, JUNE_END, user_id=1)
        total = await port.get_total_expenses(1, JUNE_START, JUNE_END, user_id=1)

        assert sum(per_category.values()) == 100.0
        assert total == Decimal("350.0")

    @respx.mock
    async def test_float_total_does_not_leak_binary_error(self, port) -> None:
        """Decimal(str(x)), ikke Decimal(x) — ellers bliver 0.1 til 0.1000000000000000055…"""
        payload = {**JUNE_PAYLOAD, "total_expenses": 0.1}
        respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=payload))

        assert await port.get_total_expenses(1, JUNE_START, JUNE_END, user_id=1) == Decimal("0.1")


class TestFailClosed:
    """Begge metoder skal rejse, så close_month aldrig lukker på et gæt."""

    @pytest.mark.parametrize("status", [401, 404, 500, 503])
    @respx.mock
    async def test_non_200_raises_upstream_unavailable(self, port, status) -> None:
        from app.domain.exceptions import UpstreamServiceUnavailable

        respx.get(OVERVIEW_URL).mock(return_value=Response(status))

        with pytest.raises(UpstreamServiceUnavailable):
            await port.get_expenses_by_category(1, JUNE_START, JUNE_END, user_id=1)

    @respx.mock
    async def test_connect_error_raises_upstream_unavailable(self, port) -> None:
        from app.domain.exceptions import UpstreamServiceUnavailable

        respx.get(OVERVIEW_URL).mock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(UpstreamServiceUnavailable):
            await port.get_total_expenses(1, JUNE_START, JUNE_END, user_id=1)

    @respx.mock
    async def test_timeout_raises_upstream_unavailable(self, port) -> None:
        from app.domain.exceptions import UpstreamServiceUnavailable

        respx.get(OVERVIEW_URL).mock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(UpstreamServiceUnavailable):
            await port.get_total_expenses(1, JUNE_START, JUNE_END, user_id=1)


class TestRequestShape:
    @respx.mock
    async def test_sends_account_and_period_and_auth(self, port) -> None:
        route = respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=JUNE_PAYLOAD))

        await port.get_expenses_by_category(42, JUNE_START, JUNE_END, user_id=7)

        assert route.called
        request = route.calls[0].request
        assert request.url.params["account_id"] == "42"
        assert request.url.params["start_date"] == "2026-06-01"
        assert request.url.params["end_date"] == "2026-06-30"
        assert request.headers["authorization"].startswith("Bearer ")

    @respx.mock
    async def test_no_limit_parameter_is_sent(self, port) -> None:
        """Regressionsværn mod P1-13.

        Den gamle adapter fejlede fordi den ikke satte 'limit' på et pagineret
        endpoint. Analytics aggregerer server-side og har ingen sidegrænse, så
        et 'limit' her ville betyde at nogen havde peget adapteren tilbage mod
        et listeendpoint.
        """
        route = respx.get(OVERVIEW_URL).mock(return_value=Response(200, json=JUNE_PAYLOAD))

        await port.get_total_expenses(1, JUNE_START, JUNE_END, user_id=1)

        assert "limit" not in route.calls[0].request.url.params
