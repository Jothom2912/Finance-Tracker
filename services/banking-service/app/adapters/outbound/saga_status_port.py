"""HTTP adapter for saga-service's status API (P3-14 sync-claim conflicts).

Forwards the calling user's own JWT — the status API is owner-checked
(P1-04), and the caller owns the connection and hence the saga. Every
failure mode maps to ``None`` ("status unknown"): the service layer then
fails ACTIVE (keeps the existing claim) while the claim is fresh, so an
unreachable saga-service can never cause duplicate sagas.
"""

from __future__ import annotations

import logging

import httpx

from app.application.ports.outbound import ISagaStatusPort
from app.config import settings

logger = logging.getLogger(__name__)


class SagaStatusPort(ISagaStatusPort):
    async def get_status(self, saga_id: str, bearer_token: str | None) -> str | None:
        if not bearer_token:
            return None
        url = f"{settings.SAGA_SERVICE_URL}/api/v1/sagas/{saga_id}"
        try:
            async with httpx.AsyncClient(timeout=settings.SAGA_SERVICE_TIMEOUT) as client:
                response = await client.get(url, headers={"Authorization": bearer_token})
        except httpx.HTTPError:
            logger.warning("saga_status_port: kunne ikke nå saga-service for saga %s", saga_id)
            return None
        if response.status_code != 200:
            logger.warning(
                "saga_status_port: got %s from saga-service for saga %s",
                response.status_code,
                saga_id,
            )
            return None
        status = response.json().get("status")
        return status if isinstance(status, str) else None
