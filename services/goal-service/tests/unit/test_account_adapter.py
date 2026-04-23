from __future__ import annotations

import pytest
import httpx

from app.adapters.outbound.account_adapter import UserServiceAccountAdapter


@pytest.mark.asyncio()
async def test_exists_returns_true_when_user_service_reports_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-internal-api-key") == "test-internal-key"
        return httpx.Response(status_code=200, json={"exists": True})

    transport = httpx.MockTransport(_handler)

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    adapter = UserServiceAccountAdapter(
        base_url="http://user-service:8001",
        api_key="test-internal-key",
        timeout=1.0,
    )

    assert await adapter.exists(1) is True


@pytest.mark.asyncio()
async def test_exists_returns_false_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, json={"detail": "not found"})

    transport = httpx.MockTransport(_handler)

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    adapter = UserServiceAccountAdapter(
        base_url="http://user-service:8001",
        api_key="test-internal-key",
        timeout=1.0,
    )

    assert await adapter.exists(123) is False


@pytest.mark.asyncio()
async def test_exists_returns_false_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get(self, *_args, **_kwargs):
            raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    adapter = UserServiceAccountAdapter(
        base_url="http://user-service:8001",
        api_key="test-internal-key",
        timeout=0.1,
    )

    assert await adapter.exists(77) is False
