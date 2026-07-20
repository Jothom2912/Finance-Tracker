"""HTTP adapter to account-service for owner resolution.

``budget.month_closed`` carries only ``account_id`` (no ``user_id``), so we
resolve the owner the same way goal-service does:
``GET /api/v1/internal/accounts/{id}/owner`` with the internal API key.
"""

from __future__ import annotations

import httpx

from app.application.ports.outbound import IAccountOwnerPort
from app.domain.exceptions import AccountNotFound, AccountOwnerUnavailable


class AccountServiceAdapter(IAccountOwnerPort):
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def get_owner_user_id(self, account_id: int) -> int:
        headers = {"x-internal-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/internal/accounts/{account_id}/owner",
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise AccountOwnerUnavailable() from exc

        if response.status_code == 404:
            raise AccountNotFound(account_id)
        if response.status_code == 200:
            return int(response.json()["user_id"])
        raise AccountOwnerUnavailable()
