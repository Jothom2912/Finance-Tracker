"""HTTP client for fetching transactions from transaction-service."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import httpx
from pydantic import BaseModel, ConfigDict

from app.config import settings

logger = logging.getLogger(__name__)


class TransactionDTO(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=False)

    id: int
    user_id: int
    account_id: int
    account_name: str
    category_id: int | None = None
    category_name: str | None = None
    amount: Decimal
    transaction_type: str
    description: str | None = None
    date: date


async def fetch_user_transactions(
    token: str,
    *,
    limit: int = 200,
) -> list[TransactionDTO]:
    """Fetch all transactions for the authenticated user.

    Paginates through the transaction-service API using skip/limit
    until all transactions are retrieved.
    """
    all_transactions: list[TransactionDTO] = []
    skip = 0

    async with httpx.AsyncClient(
        base_url=settings.TRANSACTION_SERVICE_URL,
        timeout=30.0,
    ) as client:
        while True:
            resp = await client.get(
                "/api/v1/transactions/",
                params={"skip": skip, "limit": limit},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            batch = [TransactionDTO.model_validate(t) for t in resp.json()]

            if not batch:
                break

            all_transactions.extend(batch)
            skip += limit

            if len(batch) < limit:
                break

    logger.info("Fetched %d transactions for ingest", len(all_transactions))
    return all_transactions
