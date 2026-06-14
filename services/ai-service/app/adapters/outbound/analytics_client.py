"""Analytics HTTP client — fetches structured data from gateway-service and budget-service.

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

_EXPENSE_PAGE_SIZE = 200


def _raise_for_status(resp: httpx.Response) -> None:
    """Translate HTTP errors into typed domain exceptions."""
    if resp.is_success:
        return
    code = resp.status_code
    body = resp.text[:200]
    if code in (401, 403):
        raise AnalyticsAuthError(
            f"Auth failed ({code}): {body}", status_code=code,
        )
    if code == 404:
        raise AnalyticsNotFoundError(
            f"Not found ({code}): {body}", status_code=code,
        )
    if code >= 500:
        raise AnalyticsServiceUnavailableError(
            f"Service error ({code}): {body}", status_code=code,
        )
    raise AnalyticsError(
        f"Unexpected HTTP {code}: {body}", status_code=code,
    )


class AnalyticsClient:
    def __init__(self, token: str, account_id: int) -> None:
        self._token = token
        self._account_id = account_id
        self._headers = {
            "Authorization": f"Bearer {token}",
            "X-Account-ID": str(account_id),
        }

    async def get_largest_expenses(
        self,
        period: str,
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> tuple[list[TransactionItem], float]:
        """Fetch expenses for a period, sorted by amount descending.

        Returns (items, elapsed_ms).

        Assumes ≤200 expense transactions per month per user. If this limit is
        hit, a warning is logged — the largest expense could fall outside the
        window. Correct fix requires server-side sort_by=amount support or
        paginated fetching.
        """
        t0 = time.monotonic()
        start_date, end_date = _period_to_date_range(period)

        params: dict[str, str | int] = {
            "start_date": start_date,
            "end_date": end_date,
            "transaction_type": "expense",
            "limit": _EXPENSE_PAGE_SIZE,
        }

        async with httpx.AsyncClient(
            base_url=settings.TRANSACTION_SERVICE_URL,
            timeout=15.0,
        ) as client:
            resp = await client.get(
                "/api/v1/transactions/",
                params=params,
                # transaction-service uses JWT user_id for filtering, not X-Account-ID
                headers={"Authorization": f"Bearer {self._token}"},
            )
            _raise_for_status(resp)

        raw_items = resp.json()

        if len(raw_items) >= _EXPENSE_PAGE_SIZE:
            logger.warning(
                "Hit expense page limit (%d) for period %s — largest expense "
                "may be missing from results. Consider paginated fetching.",
                _EXPENSE_PAGE_SIZE,
                period,
            )

        items = [
            TransactionItem(
                id=t["id"],
                date=t["date"],
                amount=abs(float(t["amount"])),
                category=t.get("category_name") or "Ukategoriseret",
                description=t.get("description") or "",
            )
            for t in raw_items
        ]

        if category:
            items = [i for i in items if i.category.lower() == category.lower()]

        items.sort(key=lambda i: i.amount, reverse=True)
        result = items[:limit]
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info("Fetched %d largest expenses in %.0fms", len(result), elapsed_ms)
        return result, elapsed_ms

    async def get_category_breakdown(
        self,
        period: str,
    ) -> tuple[list[CategoryBreakdownItem], float]:
        """Fetch expense breakdown by category from gateway-service dashboard.

        Returns (items, elapsed_ms).
        """
        t0 = time.monotonic()
        start_date, end_date = _period_to_date_range(period)

        async with httpx.AsyncClient(
            base_url=settings.GATEWAY_SERVICE_URL,
            timeout=15.0,
        ) as client:
            resp = await client.get(
                "/api/v1/dashboard/overview/",
                params={"start_date": start_date, "end_date": end_date},
                headers=self._headers,
            )
            _raise_for_status(resp)

        data = resp.json()
        expenses_by_cat: dict[str, float] = data.get("expenses_by_category", {})
        total = sum(expenses_by_cat.values()) or 1.0

        items = [
            CategoryBreakdownItem(
                category=cat,
                amount=amt,
                percentage=round(amt / total * 100, 1),
            )
            for cat, amt in sorted(
                expenses_by_cat.items(), key=lambda x: x[1], reverse=True
            )
        ]

        elapsed_ms = (time.monotonic() - t0) * 1000
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
        t0 = time.monotonic()
        year, month = period.split("-")

        async with httpx.AsyncClient(
            base_url=settings.BUDGET_SERVICE_URL,
            timeout=15.0,
        ) as client:
            resp = await client.get(
                "/api/v1/monthly-budgets/summary",
                params={"month": int(month), "year": int(year)},
                headers=self._headers,
            )
            _raise_for_status(resp)

        data = resp.json()
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

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info("Fetched budget status in %.0fms", elapsed_ms)
        return payload, elapsed_ms


def _period_to_date_range(period: str) -> tuple[str, str]:
    """Convert YYYY-MM to (start_date, end_date) inclusive."""
    year, month = int(period[:4]), int(period[5:7])
    last_day = calendar.monthrange(year, month)[1]
    return f"{period}-01", f"{period}-{last_day:02d}"
