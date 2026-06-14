from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import httpx

from app.application.ports.outbound import IAnalyticsReadRepository
from app.config import TRANSACTION_SERVICE_TIMEOUT, TRANSACTION_SERVICE_URL

logger = logging.getLogger(__name__)


class HttpAnalyticsReadRepository(IAnalyticsReadRepository):

    def __init__(self, auth_header: str) -> None:
        self._auth_header = auth_header
        self._base = TRANSACTION_SERVICE_URL.rstrip("/")
        self._timeout = TRANSACTION_SERVICE_TIMEOUT

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._auth_header:
            h["Authorization"] = self._auth_header
        return h

    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base}/api/v1/transactions/",
                params={"account_id": account_id},
                headers=self._headers(),
            )
            resp.raise_for_status()
            rows = resp.json()

        result: list[dict] = []
        for row in rows:
            raw_date = row.get("date")
            row_date: Optional[date] = None
            if raw_date is not None:
                if isinstance(raw_date, str):
                    try:
                        row_date = date.fromisoformat(raw_date)
                    except ValueError:
                        logger.warning(
                            "Unparseable date '%s' on transaction %s — skipping row",
                            raw_date,
                            row.get("id", "?"),
                        )
                        continue
                elif isinstance(raw_date, date):
                    row_date = raw_date
                else:
                    logger.warning(
                        "Unexpected date type %s on transaction %s — skipping row",
                        type(raw_date).__name__,
                        row.get("id", "?"),
                    )
                    continue
            else:
                logger.warning(
                    "NULL date on transaction %s — skipping row",
                    row.get("id", "?"),
                )
                continue

            if start_date and row_date < start_date:
                continue
            if end_date and row_date > end_date:
                continue

            result.append({
                "idTransaction": row.get("id"),
                "amount": row.get("amount", 0),
                "description": row.get("description"),
                "date": raw_date,
                "type": row.get("transaction_type", ""),
                "Category_idCategory": row.get("category_id"),
                "Account_idAccount": row.get("account_id"),
                "categorization_tier": row.get("categorization_tier"),
            })

        return result

    def get_categories(self) -> list[dict]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base}/api/v1/categories/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            rows = resp.json()

        return [
            {
                "idCategory": row.get("id"),
                "name": row.get("name"),
                "type": row.get("type"),
            }
            for row in rows
        ]
