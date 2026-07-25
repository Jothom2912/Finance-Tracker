from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from app.application.ports.outbound import ISpendPort
from app.auth import make_service_auth_header
from app.config import settings
from app.domain.exceptions import UpstreamServiceUnavailable

logger = logging.getLogger(__name__)


class AnalyticsSpendPort(ISpendPort):
    """Forbrug fra analytics-service — ejeren af de kanoniske regler (ADR-0004).

    Begge metoder rammer ``/overview`` og læser hvert sit felt af samme svar:
    ``expenses_by_category`` til budgetlinjerne og ``total_expenses`` til
    månedens overskud. De to tal er *ikke* udledt af hinanden — totalen
    indeholder også det ukategoriserede, som ingen budgetlinje kan bære. Se
    ``dev-notes/decisions/2026-07-25-budget-spend-from-analytics.md``.

    Erstatter den tidligere ``TransactionPort``, som summerede transaction-
    servicens listeendpoint uden ``limit`` og dermed kun så de 50 nyeste
    rækker i perioden (P1-13).
    """

    async def _fetch_overview(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        user_id: int,
    ) -> dict[str, Any]:
        url = (
            f"{settings.ANALYTICS_SERVICE_URL}/api/v1/analytics/overview"
            f"?account_id={account_id}"
            f"&start_date={start_date.isoformat()}"
            f"&end_date={end_date.isoformat()}"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url, headers=make_service_auth_header(user_id))
                if response.status_code != 200:
                    logger.warning(
                        "analytics_port: got %s from analytics-service",
                        response.status_code,
                    )
                    raise UpstreamServiceUnavailable("analytics-service")
                return response.json()
        except httpx.HTTPError:
            logger.warning("analytics_port: kunne ikke nå analytics-service")
            raise UpstreamServiceUnavailable("analytics-service")

    async def get_expenses_by_category(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        user_id: int = 0,
    ) -> dict[int, float]:
        payload = await self._fetch_overview(account_id, start_date, end_date, user_id)

        expenses: dict[int, float] = {}
        for bucket in payload.get("expenses_by_category") or []:
            category_id = bucket.get("category_id")
            if category_id is None:
                # "Ukategoriseret"-bucketen har ingen budgetlinje at hænge på.
                # Den tælles med i get_total_expenses, ikke her.
                continue
            expenses[int(category_id)] = float(bucket.get("amount", 0.0))

        return expenses

    async def get_total_expenses(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        user_id: int = 0,
    ) -> Decimal:
        payload = await self._fetch_overview(account_id, start_date, end_date, user_id)
        # str() før Decimal: total_expenses er en JSON-float, og
        # Decimal(0.1) != Decimal("0.1").
        return Decimal(str(payload.get("total_expenses", 0)))
