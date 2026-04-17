"""HTTP client used by the banking module to push bank-synced
transactions into ``transaction-service`` instead of writing directly
to MySQL.

Auth: the client forges a short-lived JWT signed with ``SECRET_KEY``
on behalf of the transaction owner.  Transaction-service validates
the same JWT via its shared ``JWT_SECRET`` (see
``docker-compose.yml``), so both ``sub`` and ``user_id`` claims are
accepted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable

import httpx
from jose import jwt

from backend.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    TRANSACTION_SERVICE_TIMEOUT,
    TRANSACTION_SERVICE_URL,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BulkTransactionItem:
    """Serialisable shape sent to transaction-service ``/bulk``."""

    account_id: int
    account_name: str
    amount: Decimal
    transaction_type: str  # "income" | "expense"
    date: date
    category_id: int | None = None
    category_name: str | None = None
    description: str | None = None
    # Categorization-pipeline metadata.  Banking runs the rule engine
    # locally before sending the batch, then hands the labels through
    # so they survive into the projection (tier badges on dashboard).
    subcategory_id: int | None = None
    categorization_tier: str | None = None
    categorization_confidence: str | None = None


@dataclass(frozen=True)
class BulkImportResult:
    """Mirror of transaction-service's ``BulkCreateResultDTO``."""

    imported: int
    duplicates_skipped: int
    errors: int
    imported_ids: list[int]


class TransactionServiceError(RuntimeError):
    """Raised when transaction-service returns a non-2xx response."""


class TransactionServiceClient:
    """Minimal HTTP client against ``transaction-service``.

    Intentionally narrow surface: the banking module only needs
    ``bulk_import``.  Other operations (create one, list, etc.) are
    already reachable via the service's public API from the frontend.
    """

    def __init__(
        self,
        base_url: str = TRANSACTION_SERVICE_URL,
        timeout: float = TRANSACTION_SERVICE_TIMEOUT,
        secret_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._secret_key = secret_key or SECRET_KEY

    # ── token minting ───────────────────────────────────────────────

    def _build_service_token(self, user_id: int) -> str:
        """Mint a short-lived JWT for service-to-service calls.

        Transaction-service reads the ``sub`` claim; the monolith's
        existing :func:`backend.auth.create_access_token` uses the
        same algorithm + secret.  We sign directly to avoid depending
        on user lookups (this client doesn't know usernames).
        """
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "user_id": user_id,
            "iss": "monolith.banking",
            "exp": expire,
        }
        return jwt.encode(payload, self._secret_key, algorithm=ALGORITHM)

    # ── API surface ─────────────────────────────────────────────────

    def bulk_import(
        self,
        user_id: int,
        items: Iterable[BulkTransactionItem],
        skip_duplicates: bool = True,
    ) -> BulkImportResult:
        """Synchronously POST a batch of transactions to
        ``/api/v1/transactions/bulk``.

        Runs under a normal (sync) FastAPI request thread, so we use
        the blocking ``httpx.Client`` and create one per call to keep
        the surface simple.  If this gets called from hot paths
        consider pooling at module scope.
        """
        payload = {
            "skip_duplicates": skip_duplicates,
            "items": [
                {
                    "account_id": item.account_id,
                    "account_name": item.account_name,
                    "amount": str(item.amount),
                    "transaction_type": item.transaction_type,
                    "date": item.date.isoformat(),
                    "category_id": item.category_id,
                    "category_name": item.category_name,
                    "description": item.description,
                    "subcategory_id": item.subcategory_id,
                    "categorization_tier": item.categorization_tier,
                    "categorization_confidence": item.categorization_confidence,
                }
                for item in items
            ],
        }

        if not payload["items"]:
            return BulkImportResult(
                imported=0,
                duplicates_skipped=0,
                errors=0,
                imported_ids=[],
            )

        url = f"{self._base_url}/api/v1/transactions/bulk"
        headers = {
            "Authorization": f"Bearer {self._build_service_token(user_id)}",
            "Content-Type": "application/json",
        }

        logger.debug(
            "Calling transaction-service bulk import: %d items for user_id=%d",
            len(payload["items"]),
            user_id,
        )

        with httpx.Client(timeout=self._timeout) as client:
            try:
                response = client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise TransactionServiceError(
                    f"transaction-service unreachable at {url}: {exc}",
                ) from exc

        if response.status_code >= 400:
            raise TransactionServiceError(
                f"transaction-service returned {response.status_code}: {response.text}",
            )

        body = response.json()
        return BulkImportResult(
            imported=body.get("imported", 0),
            duplicates_skipped=body.get("duplicates_skipped", 0),
            errors=body.get("errors", 0),
            imported_ids=body.get("imported_ids", []),
        )
