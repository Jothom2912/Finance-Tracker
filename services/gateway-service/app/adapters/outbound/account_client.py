from __future__ import annotations

import logging

import httpx

from app.config import ACCOUNT_SERVICE_TIMEOUT, ACCOUNT_SERVICE_URL

logger = logging.getLogger(__name__)


class AccountClient:

    def __init__(self, auth_header: str) -> None:
        self._auth_header = auth_header
        self._base = ACCOUNT_SERVICE_URL.rstrip("/")
        self._timeout = ACCOUNT_SERVICE_TIMEOUT

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._auth_header:
            h["Authorization"] = self._auth_header
        return h

    def get_budget_start_day(self, account_id: int) -> int:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    f"{self._base}/api/v1/accounts/{account_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return int(data.get("budget_start_day", 1))
        except httpx.ConnectError as exc:
            logger.warning(
                "account-service unreachable for budget_start_day (account=%s), "
                "falling back to default 1: %s",
                account_id,
                exc,
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "account-service timeout for budget_start_day (account=%s), "
                "falling back to default 1: %s",
                account_id,
                exc,
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "account-service returned %d for budget_start_day (account=%s), "
                "falling back to default 1: %s",
                exc.response.status_code,
                account_id,
                exc.response.text[:200],
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "account-service returned unexpected payload for budget_start_day "
                "(account=%s), falling back to default 1: %s",
                account_id,
                exc,
            )
        return 1
