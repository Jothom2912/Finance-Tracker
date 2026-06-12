from __future__ import annotations

import httpx

from app.application.ports.outbound import IAccountPort
from app.domain.exceptions import BankAccountNotOwned


class AccountServiceAdapter(IAccountPort):
    """Verifies account ownership and fetches account metadata via account-service."""

    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"x-internal-api-key": self._api_key}

    async def get_owner_user_id(self, account_id: int) -> int:
        user_id, _ = await self.get_account_info(account_id)
        return user_id

    async def get_account_info(self, account_id: int) -> tuple[int, str]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/internal/accounts/{account_id}/owner",
                    headers=self._headers(),
                )
        except httpx.RequestError:
            raise BankAccountNotOwned(account_id)
        if response.status_code == 404:
            raise BankAccountNotOwned(account_id)
        if response.status_code != 200:
            raise BankAccountNotOwned(account_id)
        payload = response.json()
        return int(payload["user_id"]), str(payload.get("account_name") or "Account")
