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

from app.config import settings
from app.dependencies import get_banking_service
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

    async def list_connections(self, account_id: int) -> list[dict]:
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
