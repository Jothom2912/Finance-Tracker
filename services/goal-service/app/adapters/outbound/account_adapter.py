from __future__ import annotations

import httpx


class UserServiceAccountAdapter:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def exists(self, user_id: int) -> bool:
        headers = {"x-internal-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/users/{user_id}/exists",
                    headers=headers,
                )
            return response.status_code == 200 and response.json().get("exists") is True
        except httpx.RequestError:
            return False
