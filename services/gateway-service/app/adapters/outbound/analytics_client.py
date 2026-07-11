"""HTTP-klient mod analytics-service (ES-backed read-side).

DTO-formerne er koordineret 1:1 med analytics-servicens response-modeller
(snake_case JSON), så mapping er ren model_validate.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

import httpx

from app.application.dto import FinancialOverview, MonthlyExpenses, TransactionProjection
from app.application.ports.outbound import IFinancialAnalyticsPort
from app.config import ANALYTICS_SERVICE_TIMEOUT, ANALYTICS_SERVICE_URL

logger = logging.getLogger(__name__)


class AnalyticsServiceUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Analytics-læsesiden er utilgængelig. Prøv igen senere.")


class HttpFinancialAnalyticsRepository(IFinancialAnalyticsPort):
    def __init__(self, auth_header: str, transport: httpx.BaseTransport | None = None) -> None:
        self._auth_header = auth_header
        self._base = ANALYTICS_SERVICE_URL.rstrip("/")
        self._timeout = ANALYTICS_SERVICE_TIMEOUT
        self._transport = transport  # test-injektion (httpx.MockTransport)

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        headers: dict[str, str] = {}
        if self._auth_header:
            headers["Authorization"] = self._auth_header
        clean_params = {k: v for k, v in params.items() if v is not None}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                resp = client.get(
                    f"{self._base}/api/v1/analytics{path}",
                    params=clean_params,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 503:
                raise AnalyticsServiceUnavailable() from exc
            raise
        except httpx.TransportError as exc:
            raise AnalyticsServiceUnavailable() from exc

    def get_financial_overview(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverview:
        data = self._get(
            "/overview",
            {
                "account_id": account_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        )
        return FinancialOverview.model_validate(data)

    def get_expenses_by_month(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        budget_start_day: int = 1,
    ) -> list[MonthlyExpenses]:
        data = self._get(
            "/expenses-by-month",
            {
                "account_id": account_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "budget_start_day": budget_start_day,
            },
        )
        return [MonthlyExpenses.model_validate(row) for row in data]

    def list_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TransactionProjection]:
        data = self._get(
            "/transactions",
            {
                "account_id": account_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "category_id": category_id,
                "tx_type": tx_type,
                "limit": limit,
            },
        )
        return [TransactionProjection.model_validate(item) for item in data["items"]]
