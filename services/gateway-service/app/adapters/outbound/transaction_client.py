from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import httpx

from app.application.ports.outbound import IAnalyticsReadRepository
from app.config import (
    TRANSACTION_PAGE_SIZE,
    TRANSACTION_SERVICE_TIMEOUT,
    TRANSACTION_SERVICE_URL,
)

logger = logging.getLogger(__name__)

# Hard cap on the pagination loop so a misbehaving upstream can never
# spin the gateway forever (100 pages * TRANSACTION_PAGE_SIZE rows).
MAX_TRANSACTION_PAGES = 100


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
        base_params: dict[str, object] = {"account_id": account_id}
        if start_date is not None:
            base_params["start_date"] = start_date.isoformat()
        if end_date is not None:
            base_params["end_date"] = end_date.isoformat()

        rows: list[dict] = []
        with httpx.Client(timeout=self._timeout) as client:
            for page in range(MAX_TRANSACTION_PAGES):
                resp = client.get(
                    f"{self._base}/api/v1/transactions/",
                    params={
                        **base_params,
                        "skip": page * TRANSACTION_PAGE_SIZE,
                        "limit": TRANSACTION_PAGE_SIZE,
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                page_rows = resp.json()
                rows.extend(page_rows)
                if len(page_rows) < TRANSACTION_PAGE_SIZE:
                    break
            else:
                logger.warning(
                    "Hit the %s-page cap fetching transactions for account %s — result may be truncated",
                    MAX_TRANSACTION_PAGES,
                    account_id,
                )

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

            # Safety net: the date range is also sent upstream as query
            # params, but keep filtering client-side so behavior is
            # identical even against a transaction-service that ignores them.
            if start_date and row_date < start_date:
                continue
            if end_date and row_date > end_date:
                continue

            # Normalized keys — legacy monolith renames (idTransaction,
            # Category_idCategory, ...) were removed with ADR-003.
            result.append(
                {
                    "id": row.get("id"),
                    "amount": row.get("amount", 0),
                    "description": row.get("description"),
                    "date": raw_date,
                    "type": row.get("transaction_type", ""),
                    "category_id": row.get("category_id"),
                    "category_name": row.get("category_name"),
                    "subcategory_id": row.get("subcategory_id"),
                    "subcategory_name": row.get("subcategory_name"),
                    "account_id": row.get("account_id"),
                    "categorization_tier": row.get("categorization_tier"),
                }
            )

        return result
