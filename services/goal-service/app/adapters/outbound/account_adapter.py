"""
Anti-corruption layer for Account domain.
Allows Goal domain to check account existence without coupling to Account internals.
"""

import logging

import httpx

from app.application.ports.outbound import IAccountPort

logger = logging.getLogger(__name__)


class UserServiceAccountAdapter(IAccountPort):
    """HTTP adapter that validates IDs against user-service."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def exists(self, user_id: int) -> bool:
        url = f"{self._base_url}/api/v1/users/{user_id}/exists"
        headers = {"x-internal-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("User validation request failed for user_id=%s: %s", user_id, exc)
            return False

        if response.status_code != 200:
            logger.warning(
                "User validation returned unexpected status for user_id=%s: %s",
                user_id,
                response.status_code,
            )
            return False

        payload = response.json()
        return bool(payload.get("exists", False))


class MockAccountAdapter(IAccountPort):
    """Mock implementation of account port for development."""

    async def exists(self, user_id: int) -> bool:
        """Check if account exists."""
        # TODO: Implement with real service call to user-service
        # For now, return True for all accounts
        return True
