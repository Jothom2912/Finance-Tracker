"""Route-level tests for ``POST /api/v1/bank/connections/{id}/sync``.

Focus is the exception-to-HTTP-status mapping: each known domain
exception must map to its intended status, and *any* unclassified
error must propagate to FastAPI's default 500 handler rather than be
laundered into a misleading 404 or 502.  The positive-control test on
``RuntimeError`` is deliberately present so a future reviewer who
adds a catch-all ``except Exception`` will break this test and think
twice.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.banking.adapters.outbound.transaction_service_client import (
    TransactionServiceError,
)
from backend.banking.application.service import BankingService, SyncResult
from backend.banking.domain.exceptions import (
    BankAccountReferenceInvalid,
    BankConnectionInactive,
    BankConnectionNotFound,
)
from backend.banking.presentation.rest_api import _get_banking_service
from backend.main import app
from fastapi.testclient import TestClient

SYNC_URL = "/api/v1/bank/connections/10/sync"


def _override_service_with(behavior, *, raise_server_exceptions: bool = True) -> TestClient:
    """Install a ``BankingService`` stub whose ``sync_transactions``
    returns (or raises) the supplied ``behavior``, then return a
    freshly-wrapped TestClient.  ``TestClient(app)`` is constructed
    here (not in a fixture) because the ``test_client`` fixture in
    ``conftest.py`` also installs DB overrides we don't need — these
    tests never touch the real DB, they just verify HTTP mapping.

    ``raise_server_exceptions=False`` is needed for the positive
    control on uncaught exceptions: TestClient re-raises by default
    so developers can see the traceback, but in production Starlette
    converts uncaught exceptions to a 500 response.  Disabling the
    re-raise gives us the production behaviour.
    """
    mock_service = MagicMock(spec=BankingService)
    if isinstance(behavior, Exception):
        mock_service.sync_transactions.side_effect = behavior
    else:
        mock_service.sync_transactions.return_value = behavior

    app.dependency_overrides[_get_banking_service] = lambda: mock_service
    client = TestClient(app, raise_server_exceptions=raise_server_exceptions)
    return client


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


class TestSyncRouteExceptionMapping:
    def test_bank_connection_not_found_maps_to_404(self) -> None:
        client = _override_service_with(BankConnectionNotFound(10))

        response = client.post(SYNC_URL)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_bank_connection_inactive_maps_to_409(self) -> None:
        """409 (Conflict) — resource exists but state forbids the
        operation.  Distinct from 404 so the frontend can show a
        "reconnect bank" CTA.
        """
        client = _override_service_with(BankConnectionInactive(10, "disconnected"))

        response = client.post(SYNC_URL)

        assert response.status_code == 409
        assert "disconnected" in response.json()["detail"].lower()

    def test_bank_account_reference_invalid_maps_to_500(self) -> None:
        """Internal invariant breach — map to 500, not 404.  Caller
        can't fix this; it's our own data integrity problem.
        """
        client = _override_service_with(BankAccountReferenceInvalid(777))

        response = client.post(SYNC_URL)

        assert response.status_code == 500

    def test_transaction_service_error_maps_to_502(self) -> None:
        """Upstream microservice is down — 502 Bad Gateway signals
        that our service is reachable but its dependency isn't.
        """
        client = _override_service_with(
            TransactionServiceError("connection refused"),
        )

        response = client.post(SYNC_URL)

        assert response.status_code == 502
        assert "transaction-service" in response.json()["detail"].lower()

    def test_unclassified_runtime_error_bubbles_to_500(self) -> None:
        """Positive control on the 'no catch-all' principle: a
        ``RuntimeError`` that nobody mapped explicitly must reach
        Starlette's default server-error handler, which returns 500.
        If a future reviewer adds ``except Exception -> 502`` to the
        route, this test breaks and forces the trade-off to be made
        consciously.
        """
        client = _override_service_with(
            RuntimeError("unexpected kaboom"),
            raise_server_exceptions=False,
        )

        response = client.post(SYNC_URL, json={})

        assert response.status_code == 500

    def test_successful_sync_includes_parse_skipped(self) -> None:
        """Parse-skip count must reach the API response — not just
        land in a WARNING log.  A sync that skipped 40 of 200
        transactions is a failure the user deserves to see.
        """
        result = SyncResult(
            total_fetched=2,
            new_imported=2,
            duplicates_skipped=0,
            errors=0,
            parse_skipped=5,
        )
        client = _override_service_with(result)

        response = client.post(SYNC_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["parse_skipped"] == 5
        assert body["total_fetched"] == 2
