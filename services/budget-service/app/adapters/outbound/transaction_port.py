from __future__ import annotations

import logging
from datetime import date

import httpx

from app.application.ports.outbound import ITransactionPort
from app.config import settings

logger = logging.getLogger(__name__)


class TransactionPort(ITransactionPort):
    """HTTP adapter til transaction-service."""

    async def get_expenses_by_category(
        self, account_id: int, start_date: date, end_date: date,
    ) -> dict[int, float]:
        url = (
            f"{settings.TRANSACTION_SERVICE_URL}/api/v1/transactions"
            f"?account_id={account_id}"
            f"&start_date={start_date.isoformat()}"
            f"&end_date={end_date.isoformat()}"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        "transaction_port: got %s from transaction-service",
                        response.status_code,
                    )
                    return {}
                transactions = response.json()
        except httpx.HTTPError:
            logger.warning("transaction_port: kunne ikke nå transaction-service")
            return {}

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
