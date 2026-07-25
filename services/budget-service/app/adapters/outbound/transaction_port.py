from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import httpx

from app.application.ports.outbound import ISpendPort
from app.auth import make_service_auth_header
from app.config import settings
from app.domain.exceptions import UpstreamServiceUnavailable

logger = logging.getLogger(__name__)


class TransactionPort(ISpendPort):
    """HTTP adapter til transaction-service."""

    async def get_expenses_by_category(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        user_id: int = 0,
    ) -> dict[int, float]:
        url = (
            f"{settings.TRANSACTION_SERVICE_URL}/api/v1/transactions"
            f"?account_id={account_id}"
            f"&start_date={start_date.isoformat()}"
            f"&end_date={end_date.isoformat()}"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(url, headers=make_service_auth_header(user_id))
                if response.status_code != 200:
                    logger.warning(
                        "transaction_port: got %s from transaction-service",
                        response.status_code,
                    )
                    raise UpstreamServiceUnavailable("transaction-service")
                transactions = response.json()
        except httpx.HTTPError:
            logger.warning("transaction_port: kunne ikke nå transaction-service")
            raise UpstreamServiceUnavailable("transaction-service")

        expenses: dict[int, float] = {}
        for tx in transactions:
            cat_id = tx.get("category_id")
            if cat_id is None:
                continue
            amount = abs(float(tx.get("amount", 0)))
            tx_type = tx.get("transaction_type", "")
            if tx_type == "expense":
                expenses[cat_id] = expenses.get(cat_id, 0.0) + amount

        return expenses

    async def get_total_expenses(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        user_id: int = 0,
    ) -> Decimal:
        """Summen af de kategoriserede buckets — dvs. præcis dagens adfærd.

        Bevidst *ikke* korrekt: ukategoriseret forbrug udelades, ligesom
        ``close_month`` har gjort hidtil. Denne adapter er på vej ud (P1-13
        step 6) og implementerer kun metoden for at forblive instantierbar,
        så udskiftningen kan rulles tilbage ved at skifte composition root.
        """
        expenses = await self.get_expenses_by_category(account_id, start_date, end_date, user_id=user_id)
        return sum((Decimal(str(v)) for v in expenses.values()), Decimal(0))
