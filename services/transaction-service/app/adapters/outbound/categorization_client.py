"""HTTP client for categorization-service.

Calls the sync /categorize endpoint (tier 1 rule engine) during
transaction creation.  Degrades gracefully: if categorization-service
is down or slow (>500ms), returns None and the transaction is saved
without categorization metadata.  The async consumer in
categorization-service will pick it up via the transaction.created event.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Direction is sent explicitly: our amount is an unsigned magnitude, so the
# categorizer cannot infer it from the sign without reading every row as
# incoming and skipping the outgoing rules (TAX-14).
Direction = Literal["incoming", "outgoing"]


@dataclass(frozen=True)
class CategorizationResult:
    category_id: int
    subcategory_id: int
    merchant_id: int | None
    tier: str
    confidence: str
    target_key: str | None = None


class CategorizationClient:
    """Sync HTTP client to categorization-service /categorize endpoint."""

    def __init__(self) -> None:
        self._base_url = settings.CATEGORIZATION_SERVICE_URL.rstrip("/")
        self._timeout = settings.CATEGORIZATION_TIMEOUT_S
        self._headers = {"X-Internal-API-Key": settings.INTERNAL_API_KEY} if settings.INTERNAL_API_KEY else {}

    async def categorize(
        self,
        description: str,
        amount: float,
        direction: Direction,
    ) -> CategorizationResult | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/categorize/",
                    json={"description": description, "amount": amount, "direction": direction},
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()
                return CategorizationResult(
                    category_id=data["category_id"],
                    subcategory_id=data["subcategory_id"],
                    merchant_id=data.get("merchant_id"),
                    tier=data["tier"],
                    confidence=data["confidence"],
                    target_key=data.get("target_key"),
                )
        except httpx.TimeoutException:
            logger.warning(
                "Categorization-service timeout (%.1fs) for '%s' — degrading gracefully",
                self._timeout,
                description[:40],
            )
            return None
        except Exception:
            logger.warning(
                "Categorization-service unavailable for '%s' — degrading gracefully",
                description[:40],
                exc_info=True,
            )
            return None

    async def categorize_batch(
        self,
        items: list[dict],
    ) -> Sequence[CategorizationResult | None]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout * 3) as client:
                payload = [
                    {
                        "description": item["description"],
                        "amount": item["amount"],
                        "direction": item["direction"],
                    }
                    for item in items
                ]
                response = await client.post(
                    f"{self._base_url}/api/v1/categorize/batch",
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()
                results = response.json()
                return [
                    CategorizationResult(
                        category_id=r["category_id"],
                        subcategory_id=r["subcategory_id"],
                        merchant_id=r.get("merchant_id"),
                        tier=r["tier"],
                        confidence=r["confidence"],
                        target_key=r.get("target_key"),
                    )
                    for r in results
                ]
        except Exception:
            logger.warning(
                "Categorization-service batch unavailable — degrading gracefully",
                exc_info=True,
            )
            return [None] * len(items)
