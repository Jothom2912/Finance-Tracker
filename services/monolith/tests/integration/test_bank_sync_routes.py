"""Route-level tests for the banking router.

Focus is the exception-to-HTTP-status mapping: each known typed
exception — domain (``BankConnectionNotFound`` etc.) or adapter
(``BankConfigError``, ``BankApiUnavailable``, ``BankAuthorizationError``)
— must map to its intended status, and *any* unclassified error must
propagate to FastAPI's default 500 handler rather than be laundered
into a misleading 404 or 502.  The positive-control tests on
``RuntimeError`` are deliberately present so a future reviewer who
adds a catch-all ``except Exception`` will break this test and think
twice.

Coverage spans three routes:
  POST /api/v1/bank/connect             - start_bank_connection
  GET  /api/v1/bank/callback            - bank_callback
  POST /api/v1/bank/connections/{id}/sync - sync_transactions
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.banking.adapters.outbound.enable_banking_client import (
    BankApiUnavailable,
    BankAuthorizationError,
    BankConfigError,
)
from backend.banking.adapters.outbound.transaction_service_client import (
    TransactionServiceError,
)
from backend.banking.application.service import BankingService, SyncResult
from backend.banking.domain.exceptions import (
    BankAccountReferenceInvalid,
    BankConnectionInactive,
    BankConnectionNotFound,
)
from backend.banking.presentation.rest_api import (
    _get_banking_service,
    _pending_authorizations,
)
from backend.main import app
from fastapi.testclient import TestClient

SYNC_URL = "/api/v1/bank/connections/10/sync"
CONNECT_URL = "/api/v1/bank/connect"
CALLBACK_URL = "/api/v1/bank/callback"


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


def _override_service_method(
    method_name: str,
    behavior,
    *,
    raise_server_exceptions: bool = True,
) -> TestClient:
    """Same shape as ``_override_service_with`` but parameterised over
    the ``BankingService`` method under test.  Used for the connect /
    callback routes which call ``start_connect`` / ``complete_connect``
    instead of ``sync_transactions``.
    """
    mock_service = MagicMock(spec=BankingService)
    attr = getattr(mock_service, method_name)
    if isinstance(behavior, Exception):
        attr.side_effect = behavior
    else:
        attr.return_value = behavior

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


# ──────────────────────────────────────────────
# POST /api/v1/bank/connect
# ──────────────────────────────────────────────


class TestConnectRouteExceptionMapping:
    """The connect route starts the OAuth flow before any user input
    has been processed — so ``BankAuthorizationError`` cannot appear
    here.  Only the config / upstream pair plus the positive control
    on uncaught errors are asserted.
    """

    _BODY = {"bank_name": "Nordea", "country": "DK", "account_id": 1}

    def test_bank_config_error_maps_to_500(self) -> None:
        """Adapter misconfigured (missing PEM / bad JWT): our deploy,
        not the caller's input.  500 is the correct signal to ops.
        """
        client = _override_service_method(
            "start_connect",
            BankConfigError("ENABLE_BANKING_APP_ID is required"),
        )

        response = client.post(CONNECT_URL, json=self._BODY)

        assert response.status_code == 500
        assert "misconfigured" in response.json()["detail"].lower()

    def test_bank_api_unavailable_maps_to_502(self) -> None:
        """Enable Banking itself is down / returned 5xx: 502 Bad Gateway
        tells the caller our service works but the upstream doesn't.
        """
        client = _override_service_method(
            "start_connect",
            BankApiUnavailable("start_authorization returned HTTP 503: bank down"),
        )

        response = client.post(CONNECT_URL, json=self._BODY)

        assert response.status_code == 502
        assert "unavailable" in response.json()["detail"].lower()

    def test_unclassified_runtime_error_bubbles_to_500(self) -> None:
        """Positive control: no catch-all here either.  If a reviewer
        reintroduces ``except Exception`` on this route, this test
        breaks — same guarantee as the sync route.
        """
        client = _override_service_method(
            "start_connect",
            RuntimeError("unexpected kaboom"),
            raise_server_exceptions=False,
        )

        response = client.post(CONNECT_URL, json=self._BODY)

        assert response.status_code == 500


# ──────────────────────────────────────────────
# GET /api/v1/bank/callback
# ──────────────────────────────────────────────


class TestCallbackRouteExceptionMapping:
    """The callback is the one route where ``BankAuthorizationError``
    is expected — it's the endpoint that hands the user-supplied
    ``auth_code`` to Enable Banking.
    """

    _STATE = "fake-state-for-tests"
    _CODE = "fake-auth-code"

    @pytest.fixture(autouse=True)
    def _register_state(self):
        """Callback short-circuits with 400 if ``state`` is not in the
        pending map.  Seed it so we reach the service-call code path.
        """
        _pending_authorizations[self._STATE] = 1
        yield
        _pending_authorizations.pop(self._STATE, None)

    def _params(self) -> dict[str, str]:
        return {"state": self._STATE, "code": self._CODE}

    def test_bank_authorization_error_maps_to_400(self) -> None:
        """The one place where a 4xx-from-upstream means caller-error.
        Raised by ``create_session`` when the auth_code is expired or
        already used — the user's remedy is to restart the flow.
        """
        client = _override_service_method(
            "complete_connect",
            BankAuthorizationError(
                "Enable Banking rejected authorization code with HTTP 400: "
                "the code may have expired or already been used"
            ),
        )

        response = client.get(CALLBACK_URL, params=self._params())

        assert response.status_code == 400
        assert "rejected" in response.json()["detail"].lower()

    def test_bank_config_error_maps_to_500(self) -> None:
        """Same as sync route: config is ours, not caller's."""
        client = _override_service_method(
            "complete_connect",
            BankConfigError("Failed to sign Enable Banking JWT"),
        )

        response = client.get(CALLBACK_URL, params=self._params())

        assert response.status_code == 500
        assert "misconfigured" in response.json()["detail"].lower()

    def test_bank_api_unavailable_maps_to_502(self) -> None:
        """Upstream 5xx or transport error — not caller's auth_code."""
        client = _override_service_method(
            "complete_connect",
            BankApiUnavailable("Enable Banking create_session unreachable"),
        )

        response = client.get(CALLBACK_URL, params=self._params())

        assert response.status_code == 502

    def test_unclassified_runtime_error_bubbles_to_500(self) -> None:
        """Positive control across the third and final banking route."""
        client = _override_service_method(
            "complete_connect",
            RuntimeError("unexpected kaboom"),
            raise_server_exceptions=False,
        )

        response = client.get(CALLBACK_URL, params=self._params())

        assert response.status_code == 500

    def test_bank_level_error_query_param_maps_to_400(self) -> None:
        """Sanity check for the pre-existing early-exit path: when
        Enable Banking itself reports an error in the redirect
        (``?error=access_denied``), no service call happens and we
        return 400 directly.  Left in place to document that the
        user-rejected path does *not* regress under the new typed-error
        mapping.
        """
        app.dependency_overrides[_get_banking_service] = lambda: MagicMock(spec=BankingService)
        client = TestClient(app)

        response = client.get(
            CALLBACK_URL,
            params={"state": self._STATE, "error": "access_denied"},
        )

        assert response.status_code == 400
        assert "access_denied" in response.json()["detail"]
