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

from datetime import datetime, timezone
from uuid import UUID

from app.config import settings
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
        {"user_id": user_id, "username": "testuser"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
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
