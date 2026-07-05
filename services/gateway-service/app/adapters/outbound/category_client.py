"""HTTP client for categorization-service's taxonomy read endpoints.

Per ADR-003 categorization-service is the single owner (and single read
source) of categories and subcategories. Keys are passed through
normalized (``id``/``name``/``type``/``display_order``) — no legacy
``idCategory`` renames.
"""

from __future__ import annotations

import logging

import httpx

from app.application.ports.outbound import ICategoryReadRepository
from app.config import CATEGORIZATION_SERVICE_TIMEOUT, CATEGORIZATION_SERVICE_URL

logger = logging.getLogger(__name__)


class CategoryClient(ICategoryReadRepository):
    def __init__(self, auth_header: str) -> None:
        self._auth_header = auth_header
        self._base = CATEGORIZATION_SERVICE_URL.rstrip("/")
        self._timeout = CATEGORIZATION_SERVICE_TIMEOUT

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._auth_header:
            h["Authorization"] = self._auth_header
        return h

    def get_categories(self) -> list[dict]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base}/api/v1/categories/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def get_subcategories(self) -> list[dict]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(
                f"{self._base}/api/v1/subcategories/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
