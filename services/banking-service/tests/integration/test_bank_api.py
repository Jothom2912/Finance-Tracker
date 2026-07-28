from __future__ import annotations

import os
from unittest.mock import AsyncMock

for key in (
    "ACTIVE_DB",
    "ELASTICSEARCH_HOST",
    "SYNC_TO_ELASTICSEARCH",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "USE_NEO4J",
    "SECRET_KEY",
):
    os.environ.pop(key, None)

os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("ENABLE_BANKING_APP_ID", "test-app")
os.environ.setdefault("ENABLE_BANKING_KEY_PATH", "dummy.pem")
os.environ.setdefault("ENABLE_BANKING_REDIRECT_URI", "http://localhost/callback")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator
from uuid import UUID

from app.config import settings
from app.database import get_db
from app.dependencies import get_banking_service
from app.domain.exceptions import BankAccountNotOwned, BankConsentExpired
from app.main import app
from fastapi.testclient import TestClient
from jose import jwt


class FakeBankingService:
    async def list_banks(self, country: str = "DK") -> list[dict]:
        return [{"name": "Test Bank", "country": country}]

    async def start_connect(self, bank_name: str, country: str, account_id: int, user_id: int) -> dict[str, str]:
        return {
            "url": f"https://bank.test/auth?bank={bank_name}&account={account_id}&user={user_id}",
            "state": "state-1",
        }

    async def list_connections(self, account_id: int, user_id: int) -> list[dict]:
        return [{"id": "connection-1", "account_id": account_id, "status": "active"}]


def make_auth_header(user_id: int = 1) -> dict[str, str]:
    token = jwt.encode(
        {
            "user_id": user_id,
            "username": "testuser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_available_banks_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/bank/available-banks")

    assert response.status_code == 401


def test_available_banks_returns_banks_for_authenticated_user() -> None:
    app.dependency_overrides[get_banking_service] = lambda: FakeBankingService()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/bank/available-banks?country=DK", headers=make_auth_header())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [{"name": "Test Bank", "country": "DK"}]


def test_connect_endpoint_uses_user_from_jwt() -> None:
    fake_service = FakeBankingService()
    fake_service.start_connect = AsyncMock(return_value={"url": "https://bank.test/auth", "state": "state-1"})
    app.dependency_overrides[get_banking_service] = lambda: fake_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/bank/connect",
                json={"bank_name": "Test Bank", "country": "DK", "account_id": 123},
                headers=make_auth_header(user_id=42),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"authorization_url": "https://bank.test/auth", "state": "state-1"}
    fake_service.start_connect.assert_awaited_once_with(
        bank_name="Test Bank",
        country="DK",
        account_id=123,
        user_id=42,
    )


def test_list_connections_passes_user_from_jwt() -> None:
    fake_service = FakeBankingService()
    fake_service.list_connections = AsyncMock(return_value=[])
    app.dependency_overrides[get_banking_service] = lambda: fake_service
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/bank/connections?account_id=123",
                headers=make_auth_header(user_id=42),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    fake_service.list_connections.assert_awaited_once_with(123, user_id=42)


def test_list_connections_denied_for_foreign_account() -> None:
    fake_service = FakeBankingService()
    fake_service.list_connections = AsyncMock(side_effect=BankAccountNotOwned(123))
    app.dependency_overrides[get_banking_service] = lambda: fake_service
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/bank/connections?account_id=123",
                headers=make_auth_header(user_id=42),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_disconnect_passes_user_from_jwt() -> None:
    connection_id = "11111111-1111-1111-1111-111111111111"
    fake_service = FakeBankingService()
    fake_service.disconnect = AsyncMock(return_value=True)
    app.dependency_overrides[get_banking_service] = lambda: fake_service
    try:
        with TestClient(app) as client:
            response = client.delete(
                f"/api/v1/bank/connections/{connection_id}",
                headers=make_auth_header(user_id=42),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    fake_service.disconnect.assert_awaited_once()
    assert fake_service.disconnect.await_args.kwargs["user_id"] == 42


def test_sync_returns_409_with_danish_reconsent_detail_when_consent_expired() -> None:
    connection_id = "11111111-1111-1111-1111-111111111111"
    fake_service = FakeBankingService()
    fake_service.start_sync_saga = AsyncMock(
        side_effect=BankConsentExpired(
            UUID(connection_id),
            datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    app.dependency_overrides[get_banking_service] = lambda: fake_service
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/bank/connections/{connection_id}/sync",
                headers=make_auth_header(user_id=42),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "samtykke er udløbet" in detail
    assert "synkronisere" in detail


def test_disconnect_denied_for_foreign_connection() -> None:
    connection_id = "11111111-1111-1111-1111-111111111111"
    fake_service = FakeBankingService()
    fake_service.disconnect = AsyncMock(side_effect=BankAccountNotOwned(123))
    app.dependency_overrides[get_banking_service] = lambda: fake_service
    try:
        with TestClient(app) as client:
            response = client.delete(
                f"/api/v1/bank/connections/{connection_id}",
                headers=make_auth_header(user_id=42),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


# ── P2-42a: BankConfigError -> 503, not 500 ────────────────────────
#
# These two deliberately do NOT override `get_banking_service`.  That is the whole
# point: `BankConfigError` is raised while FastAPI *resolves* the dependency —
# `get_banking_service` -> `_get_banking_client()` -> `EnableBankingConfig`
# (missing PEM) or `EnableBankingClient.__init__` (unreadable PEM) — so it happens
# before any route body runs.  A per-route try/except therefore cannot catch it,
# which is why `GET /connections` has none and returned a bare 500 to the
# dashboard.  Only an app-level exception handler covers this path.
#
# `get_db` IS overridden, because `get_banking_service` takes it as a dependency
# and it resolves first; the DB is not what these tests are about.


@contextmanager
def unconfigured_banking(monkeypatch_path: str = "/nonexistent/enablebanking.pem") -> Iterator[None]:
    """Force the Enable Banking client to be unconstructable, as in an unconfigured deploy."""
    import app.dependencies as deps

    original_path = settings.ENABLE_BANKING_KEY_PATH
    original_client = deps._banking_client
    settings.ENABLE_BANKING_KEY_PATH = monkeypatch_path
    # The client is a process-wide singleton; a cached one from another test would
    # hide the failure entirely.
    deps._banking_client = None
    app.dependency_overrides[get_db] = lambda: None
    try:
        yield
    finally:
        settings.ENABLE_BANKING_KEY_PATH = original_path
        deps._banking_client = original_client
        app.dependency_overrides.clear()


def test_available_banks_returns_503_when_integration_unconfigured() -> None:
    with unconfigured_banking(), TestClient(app) as client:
        response = client.get("/api/v1/bank/available-banks?country=DK", headers=make_auth_header())

    # 503, not 500: an unconfigured optional integration is unavailable, not a bug
    # in banking-service — and it is retryable, which 500 does not communicate.
    assert response.status_code == 503
    assert "detail" in response.json()


def test_list_connections_returns_503_when_integration_unconfigured() -> None:
    # This is the call the dashboard makes, and the one that had no try/except at
    # all — the 500 in finding 2026-07-28-banking-service-dead-in-ci.md.
    with unconfigured_banking(), TestClient(app) as client:
        response = client.get("/api/v1/bank/connections?account_id=123", headers=make_auth_header())

    assert response.status_code == 503
    assert "detail" in response.json()
