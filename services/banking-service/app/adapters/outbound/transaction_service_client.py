from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from jose import jwt

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BulkImportResult:
    imported: int
    duplicates_skipped: int
    errors: int
    imported_ids: list[int]


class TransactionServiceError(RuntimeError):
    pass


class TransactionServiceClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.TRANSACTION_SERVICE_URL).rstrip("/")
        self._timeout = timeout or settings.TRANSACTION_SERVICE_TIMEOUT

    def _build_service_token(self, user_id: int) -> str:
        expire = datetime.utcnow() + timedelta(minutes=30)
        payload = {
            "sub": str(user_id),
            "user_id": user_id,
            "iss": "banking-service",
            "exp": expire,
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def bulk_import(
        self,
        user_id: int,
        items: list[Any],
        skip_duplicates: bool = True,
    ) -> BulkImportResult:
        if not items:
            return BulkImportResult(
                imported=0, duplicates_skipped=0, errors=0, imported_ids=[]
            )

        payload = {"skip_duplicates": skip_duplicates, "items": items}
        url = f"{self._base_url}/api/v1/transactions/bulk"
        headers = {
            "Authorization": f"Bearer {self._build_service_token(user_id)}",
            "Content-Type": "application/json",
        }

        logger.debug(
            "Calling transaction-service bulk import: %d items for user_id=%d",
            len(items),
            user_id,
        )

        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            try:
                response = client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise TransactionServiceError(
                    f"transaction-service unreachable at {url}: {exc}"
                ) from exc

        if response.status_code >= 400:
            raise TransactionServiceError(
                f"transaction-service returned {response.status_code}: "
                f"{response.text}"
            )

        body = response.json()
        return BulkImportResult(
            imported=body.get("imported", 0),
            duplicates_skipped=body.get("duplicates_skipped", 0),
            errors=body.get("errors", 0),
            imported_ids=body.get("imported_ids", []),
        )
