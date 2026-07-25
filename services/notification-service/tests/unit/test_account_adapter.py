"""HTTP → domain-exception mapping for the owner-resolution adapter.

This adapter is the only place a live dependency is *interpreted*, and the
distinction it draws decides message fate: ``AccountNotFound`` means drop
(nobody to notify), everything else means retry/DLQ. Driven through
``httpx.MockTransport`` so the real client, base_url and headers are used.
"""

from __future__ import annotations

import httpx
import pytest
from app.adapters.outbound.account_adapter import AccountServiceAdapter
from app.domain.exceptions import (
    AccountNotFound,
    AccountOwnerAuthError,
    AccountOwnerUnavailable,
)

BASE_URL = "http://account-service:8000"
API_KEY = "test-internal-key"


def _adapter(handler: object) -> AccountServiceAdapter:
    return AccountServiceAdapter(
        base_url=BASE_URL,
        api_key=API_KEY,
        timeout=1.0,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def _responder(status_code: int, json: object | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        handler.seen = request  # type: ignore[attr-defined]
        return httpx.Response(status_code, json=json)

    return handler


async def test_200_returns_owner_and_sends_the_internal_key() -> None:
    handler = _responder(200, {"user_id": 42})
    adapter = _adapter(handler)

    assert await adapter.get_owner_user_id(7) == 42
    await adapter.aclose()

    request: httpx.Request = handler.seen  # type: ignore[attr-defined]
    assert request.url.path == "/api/v1/internal/accounts/7/owner"
    assert request.headers["x-internal-api-key"] == API_KEY


async def test_404_is_account_not_found() -> None:
    adapter = _adapter(_responder(404))
    with pytest.raises(AccountNotFound):
        await adapter.get_owner_user_id(7)
    await adapter.aclose()


async def test_500_is_unavailable() -> None:
    adapter = _adapter(_responder(500))
    with pytest.raises(AccountOwnerUnavailable):
        await adapter.get_owner_user_id(7)
    await adapter.aclose()


@pytest.mark.parametrize("status_code", [401, 403])
async def test_401_and_403_are_auth_errors_not_outages(status_code: int) -> None:
    # A rejected key must not be filed as an account-service outage.
    adapter = _adapter(_responder(status_code))
    with pytest.raises(AccountOwnerAuthError):
        await adapter.get_owner_user_id(7)
    await adapter.aclose()


async def test_transport_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    adapter = _adapter(handler)
    with pytest.raises(AccountOwnerUnavailable):
        await adapter.get_owner_user_id(7)
    await adapter.aclose()


async def test_client_is_reused_across_calls() -> None:
    # The pool must survive a call: closing it per event was the whole point
    # of the refactor, and a use-after-close would raise here.
    adapter = _adapter(_responder(200, {"user_id": 1}))
    assert await adapter.get_owner_user_id(1) == 1
    assert await adapter.get_owner_user_id(2) == 1
    assert adapter._client.is_closed is False

    await adapter.aclose()
    assert adapter._client.is_closed is True
