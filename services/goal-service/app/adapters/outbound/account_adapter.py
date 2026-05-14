from __future__ import annotations

import httpx

from app.domain.exceptions import AccountNotFoundForGoal, UpstreamServiceUnavailable


class AccountServiceAdapter:
    """Adapter for verifying account existence via account-service."""

    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def exists(self, account_id: int) -> bool:
        headers = {"x-internal-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/internal/accounts/{account_id}/exists",
                    headers=headers,
                )
            return response.status_code == 200 and response.json().get("exists") is True
        except httpx.RequestError:
            return False

    async def get_owner_user_id(self, account_id: int) -> int:
        headers = {"x-internal-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/internal/accounts/{account_id}/owner",
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise UpstreamServiceUnavailable("account-service") from exc
        if response.status_code == 404:
            raise AccountNotFoundForGoal(account_id)
        if response.status_code == 200:
            return int(response.json()["user_id"])
        raise UpstreamServiceUnavailable("account-service")
