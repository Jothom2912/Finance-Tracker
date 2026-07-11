from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import SAGA_SERVICE_TIMEOUT, SAGA_SERVICE_URL

logger = logging.getLogger(__name__)


class SagaServiceClient:
    def __init__(self, auth_header: str) -> None:
        self._auth_header = auth_header
        self._base = SAGA_SERVICE_URL.rstrip("/")
        self._timeout = SAGA_SERVICE_TIMEOUT

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._auth_header:
            h["Authorization"] = self._auth_header
        return h

    def get_saga_status(self, saga_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base}/api/v1/sagas/{saga_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
