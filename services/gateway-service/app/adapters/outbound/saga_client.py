from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import SAGA_SERVICE_TIMEOUT, SAGA_SERVICE_URL

logger = logging.getLogger(__name__)


class SagaServiceClient:
    def __init__(self) -> None:
        self._base = SAGA_SERVICE_URL.rstrip("/")
        self._timeout = SAGA_SERVICE_TIMEOUT

    def get_saga_status(self, saga_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base}/api/v1/sagas/{saga_id}")
            resp.raise_for_status()
            return resp.json()
