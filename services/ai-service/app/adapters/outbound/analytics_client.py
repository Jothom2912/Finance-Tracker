"""Structured-data HTTP client — analytics-service (ES read-store) + budget-service.

largest_expense and category_breakdown are served by analytics-service
(`/api/v1/analytics/*`, exact ES aggregations per ADR-0004 — AI-19).
budget_status stays on budget-service: budgets are not projected into ES.

Receives token and account_id per-request (constructor injection) so the port
interface stays clean of HTTP/auth concerns. Each method maps to one backend
endpoint and returns typed domain models.

TODO: inject a shared httpx.AsyncClient via constructor instead of creating one
per call — reduces connection overhead when multiple intents fire in sequence.
"""

from __future__ import annotations

import calendar
import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.domain.exceptions import (
    AnalyticsAuthError,
    AnalyticsError,
    AnalyticsNotFoundError,
    AnalyticsServiceUnavailableError,
)
from app.domain.models import (
    BudgetStatusItem,
    BudgetStatusPayload,
    CategoryBreakdownItem,
    TransactionItem,
)

logger = logging.getLogger(__name__)

# Slot-kategori er et NAVN (AI-21 mapper til id senere); indtil da filtreres
# klient-side, så vi henter en større side når kategori-filter er sat.
_CATEGORY_FILTER_PAGE_SIZE = 200


def _raise_for_status(resp: httpx.Response) -> None:
    """Translate HTTP errors into typed domain exceptions."""
    if resp.is_success:
        return
    code = resp.status_code
    body = resp.text[:200]
    if code in (401, 403):
        raise AnalyticsAuthError(
            f"Auth failed ({code}): {body}",
            status_code=code,
        )
    if code == 404:
        raise AnalyticsNotFoundError(
            f"Not found ({code}): {body}",
            status_code=code,
        )
    if code >= 500:
        raise AnalyticsServiceUnavailableError(
            f"Service error ({code}): {body}",
            status_code=code,
        )
    raise AnalyticsError(
        f"Unexpected HTTP {code}: {body}",
        status_code=code,
    )


class AnalyticsClient:
    def __init__(self, token: str, account_id: int) -> None:
        self._token = token
        self._account_id = account_id
        self._headers = {
            "Authorization": f"Bearer {token}",
            "X-Account-ID": str(account_id),
        }

    async def _get_json(
        self,
        base_url: str,
        path: str,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
            resp = await client.get(
                path,
                params=params,
                headers=headers or {"Authorization": f"Bearer {self._token}"},
            )
            _raise_for_status(resp)
        return resp.json()

    async def get_largest_expenses(
        self,
        period: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> tuple[list[TransactionItem], float]:
        """Fetch the largest expenses for a period, sorted server-side by |amount|.

        Returns (items, elapsed_ms).

        analytics-service sorts on the ES `amount_abs` field, so the result is
        exact regardless of how many expenses the period holds (the old
        transaction-service path fetched 200 rows and sorted client-side).
        """
        t0 = time.perf_counter()
        start_date, end_date = _period_to_date_range(period)

        params: dict[str, str | int] = {
            "account_id": self._account_id,
            "start_date": start_date,
            "end_date": end_date,
            "tx_type": "expense",
            "sort": "amount_desc",
            "limit": _CATEGORY_FILTER_PAGE_SIZE if category else limit,
        }

        data = await self._get_json(
            settings.ANALYTICS_SERVICE_URL,
            "/api/v1/analytics/transactions",
            params,
        )

        items = [
            TransactionItem(
                id=t["id"],
                date=t["date"],
                amount=abs(float(t["amount"])),
                category=t.get("category_name") or "Ukategoriseret",
                description=t.get("description") or "",
            )
            for t in data.get("items", [])
        ]

        if category:
            items = [i for i in items if i.category.lower() == category.lower()]
            if int(data.get("total_count", 0)) > _CATEGORY_FILTER_PAGE_SIZE:
                logger.warning(
                    "Category-filtered largest_expense over %d rows for period %s "
                    "— result may be incomplete until the slot resolves to "
                    "category_id (AI-21).",
                    _CATEGORY_FILTER_PAGE_SIZE,
                    period,
                )

        result = items[:limit]
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info("Fetched %d largest expenses in %.0fms", len(result), elapsed_ms)
        return result, elapsed_ms

    async def get_category_breakdown(
        self,
        period: str,
    ) -> tuple[list[CategoryBreakdownItem], float]:
        """Fetch expense breakdown by category from analytics-service overview.

        Returns (items, elapsed_ms).
        """
        t0 = time.perf_counter()
        start_date, end_date = _period_to_date_range(period)

        data = await self._get_json(
            settings.ANALYTICS_SERVICE_URL,
            "/api/v1/analytics/overview",
            {
                "account_id": self._account_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        # ADR-003 shape: list of {category_id, category_name, amount,
        # subcategories[]} (id-keyed aggregation, sorted by amount desc).
        expenses_by_cat: list[dict] = data.get("expenses_by_category", [])
        total = sum(e.get("amount", 0.0) for e in expenses_by_cat) or 1.0

        items = [
            CategoryBreakdownItem(
                category=e.get("category_name", "Ukategoriseret"),
                amount=e.get("amount", 0.0),
                percentage=round(e.get("amount", 0.0) / total * 100, 1),
            )
            for e in expenses_by_cat
        ]

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Fetched category breakdown (%d categories) in %.0fms",
            len(items),
            elapsed_ms,
        )
        return items, elapsed_ms

    async def get_budget_status(
        self,
        period: str,
    ) -> tuple[BudgetStatusPayload, float]:
        """Fetch budget vs actual from budget-service monthly-budgets summary.

        Returns (payload, elapsed_ms).
        """
        t0 = time.perf_counter()
        year, month = period.split("-")

        data = await self._get_json(
            settings.BUDGET_SERVICE_URL,
            "/api/v1/monthly-budgets/summary",
            {"month": int(month), "year": int(year)},
            headers=self._headers,
        )

        items = [
            BudgetStatusItem(
                category_name=item["category_name"],
                budget_amount=float(item["budget_amount"]),
                spent_amount=float(item["spent_amount"]),
                remaining_amount=float(item["remaining_amount"]),
                percentage_used=float(item["percentage_used"]),
            )
            for item in data.get("items", [])
        ]

        payload = BudgetStatusPayload(
            items=items,
            total_budget=float(data.get("total_budget", 0)),
            total_spent=float(data.get("total_spent", 0)),
            total_remaining=float(data.get("total_remaining", 0)),
            over_budget_count=int(data.get("over_budget_count", 0)),
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info("Fetched budget status in %.0fms", elapsed_ms)
        return payload, elapsed_ms


def _period_to_date_range(period: str) -> tuple[str, str]:
    """Convert YYYY-MM to (start_date, end_date) inclusive."""
    year, month = int(period[:4]), int(period[5:7])
    last_day = calendar.monthrange(year, month)[1]
    return f"{period}-01", f"{period}-{last_day:02d}"
