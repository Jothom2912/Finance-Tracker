"""HTTP adapter for IAccountResolver.

Calls account-service directly instead of reading the MySQL read-model,
avoiding the async sync delay that causes "Account ID required" errors
immediately after account creation.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from backend.shared.ports.auth_ports import IAccountResolver

logger = logging.getLogger(__name__)


class HttpAccountResolver(IAccountResolver):
    """Resolves account ownership via account-service HTTP API."""

    def __init__(self, token: str, base_url: str, timeout: float = 5.0) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def get_account_id_for_user(self, user_id: int) -> Optional[int]:
        try:
            response = httpx.get(
                f"{self._base_url}/accounts",
                headers=self._headers(),
                timeout=self._timeout,
            )
            if response.status_code == 200:
                accounts = response.json()
                if accounts:
                    return int(accounts[0].get("idAccount") or accounts[0].get("id"))
        except Exception:
            logger.exception("HttpAccountResolver.get_account_id_for_user failed")
        return None

    def verify_account_ownership(self, user_id: int, account_id: int) -> bool:
        try:
            response = httpx.get(
                f"{self._base_url}/accounts/{account_id}",
                headers=self._headers(),
                timeout=self._timeout,
            )
            return response.status_code == 200
        except Exception:
            logger.exception("HttpAccountResolver.verify_account_ownership failed")
        return False
