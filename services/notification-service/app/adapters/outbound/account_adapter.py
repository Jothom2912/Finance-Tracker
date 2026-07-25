"""HTTP adapter to account-service for owner resolution.

``budget.month_closed`` carries only ``account_id`` (no ``user_id``), so we
resolve the owner the same way goal-service does:
``GET /api/v1/internal/accounts/{id}/owner`` with the internal API key.
"""

from __future__ import annotations

import logging

import httpx

from app.application.ports.outbound import IAccountOwnerPort
from app.domain.exceptions import (
    AccountNotFound,
    AccountOwnerAuthError,
    AccountOwnerUnavailable,
)

logger = logging.getLogger(__name__)


class AccountServiceAdapter(IAccountOwnerPort):
    """Owner lookups over one long-lived connection pool.

    The adapter outlives every message (the consumer builds it once), so it
    holds a single ``AsyncClient`` instead of tearing down a pool — and with
    it the TCP handshake — per event. Callers must ``aclose()`` on shutdown.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # ``transport`` is a test seam (httpx.MockTransport); base_url, headers
        # and timeout still apply, so the URL we build stays under test.
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"x-internal-api-key": api_key},
            transport=transport,
        )

    async def get_owner_user_id(self, account_id: int) -> int:
        try:
            response = await self._client.get(f"/api/v1/internal/accounts/{account_id}/owner")
        except httpx.RequestError as exc:
            raise AccountOwnerUnavailable() from exc

        if response.status_code == 200:
            return int(response.json()["user_id"])
        if response.status_code == 404:
            raise AccountNotFound(account_id)
        if response.status_code in (401, 403):
            # Our own misconfiguration, not an upstream outage. Log it loudly
            # here because the retry ladder above only reports "handler failed"
            # — and no number of retries fixes a wrong key.
            logger.error(
                "account-service rejected the internal API key (HTTP %s, account_id=%s)",
                response.status_code,
                account_id,
            )
            raise AccountOwnerAuthError(response.status_code)
        raise AccountOwnerUnavailable()

    async def aclose(self) -> None:
        await self._client.aclose()
