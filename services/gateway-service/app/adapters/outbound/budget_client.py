from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import BUDGET_SERVICE_TIMEOUT, BUDGET_SERVICE_URL

logger = logging.getLogger(__name__)


class BudgetClient:

    def __init__(self, auth_header: str) -> None:
        self._auth_header = auth_header
        self._base = BUDGET_SERVICE_URL.rstrip("/")
        self._timeout = BUDGET_SERVICE_TIMEOUT

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._auth_header:
            h["Authorization"] = self._auth_header
        return h

    def get_budget_summary(
        self,
        account_id: int,
        month: int,
        year: int,
        budget_start_day: int,
    ) -> Optional[dict[str, Any]]:
        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                resp = client.get(
                    f"{self._base}/api/v1/monthly-budgets/summary",
                    params={
                        "account_id": account_id,
                        "month": month,
                        "year": year,
                        "budget_start_day": budget_start_day,
                    },
                    headers=self._headers(),
                )
                if resp.status_code == 401:
                    logger.warning(
                        "budget-service auth rejected (401) for budget_summary "
                        "— check token forwarding"
                    )
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as exc:
            logger.warning("budget-service unreachable for budget_summary: %s", exc)
        except httpx.TimeoutException as exc:
            logger.warning("budget-service timeout for budget_summary: %s", exc)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "budget-service returned %d for budget_summary: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "budget-service returned unexpected payload for budget_summary: %s",
                exc,
            )
        return None
