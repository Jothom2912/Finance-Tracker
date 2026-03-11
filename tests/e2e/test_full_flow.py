"""End-to-end tests for the user registration → account creation saga.

Prerequisites:
    docker compose up -d --build --wait

Run:
    pytest tests/e2e/test_full_flow.py -v -m e2e
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from jose import jwt

USER_SERVICE = "http://localhost:8001/api/v1/users"
MONOLITH = "http://localhost:8000/api/v1"

JWT_SECRET = "dev-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"

pytestmark = pytest.mark.e2e


# ── helpers ─────────────────────────────────────────────────────────


def _unique_user() -> dict[str, str]:
    uid = uuid.uuid4().hex[:8]
    return {
        "username": f"e2e_{uid}",
        "email": f"e2e_{uid}@example.com",
        "password": "SecurePass123!",
    }


def _monolith_token(user_id: int, username: str, email: str) -> str:
    """Build a JWT the monolith's ``decode_token`` accepts.

    The monolith expects ``user_id``, ``username``, ``email`` claims
    whereas user-service emits ``sub``.  In a future iteration the
    token format should be unified; this helper bridges the gap for
    e2e verification.
    """
    payload = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def _wait_for_default_account(
    client: httpx.AsyncClient,
    token: str,
    timeout: float = 15.0,
) -> dict:
    """Poll the monolith until the default account appears or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(
            f"{MONOLITH}/accounts/",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            accounts = resp.json()
            default = [a for a in accounts if a["name"] == "Default Account"]
            if default:
                return default[0]
        await asyncio.sleep(0.5)

    pytest.fail(
        "Default account was not created within timeout — "
        "the saga may not have completed.  "
        "Check consumer logs: docker compose logs consumer"
    )


# ── tests ───────────────────────────────────────────────────────────


class TestHealthChecks:
    @pytest.mark.asyncio()
    async def test_user_service_healthy(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8001/health")

        assert resp.status_code == 200
        assert resp.json()["service"] == "user-service"

    @pytest.mark.asyncio()
    async def test_monolith_healthy(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8000/health")

        assert resp.status_code == 200


class TestRegistration:
    @pytest.mark.asyncio()
    async def test_register_user_via_user_service(self) -> None:
        user = _unique_user()

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{USER_SERVICE}/register", json=user)

        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == user["username"]
        assert data["email"] == user["email"]
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio()
    async def test_duplicate_registration_returns_409(self) -> None:
        user = _unique_user()

        async with httpx.AsyncClient() as client:
            await client.post(f"{USER_SERVICE}/register", json=user)
            resp = await client.post(f"{USER_SERVICE}/register", json=user)

        assert resp.status_code == 409


class TestLogin:
    @pytest.mark.asyncio()
    async def test_login_returns_token(self) -> None:
        user = _unique_user()

        async with httpx.AsyncClient() as client:
            await client.post(f"{USER_SERVICE}/register", json=user)
            resp = await client.post(
                f"{USER_SERVICE}/login",
                json={"email": user["email"], "password": user["password"]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestSagaFlow:
    @pytest.mark.asyncio()
    async def test_full_saga_creates_default_account(self) -> None:
        """Register via user-service → consumer creates default account in
        monolith MySQL → verify account exists via monolith API."""
        user = _unique_user()

        async with httpx.AsyncClient(timeout=20.0) as client:
            reg_resp = await client.post(
                f"{USER_SERVICE}/register", json=user
            )
            assert reg_resp.status_code == 201
            user_data = reg_resp.json()
            user_id = user_data["id"]

            token = _monolith_token(
                user_id=user_id,
                username=user_data["username"],
                email=user_data["email"],
            )

            account = await _wait_for_default_account(client, token)

        assert account["name"] == "Default Account"
        assert account["User_idUser"] == user_id

    @pytest.mark.asyncio()
    async def test_login_token_works_on_user_service(self) -> None:
        """Token from user-service login is usable for /me endpoint."""
        user = _unique_user()

        async with httpx.AsyncClient() as client:
            await client.post(f"{USER_SERVICE}/register", json=user)
            login_resp = await client.post(
                f"{USER_SERVICE}/login",
                json={"email": user["email"], "password": user["password"]},
            )
            token = login_resp.json()["access_token"]

            me_resp = await client.get(
                f"{USER_SERVICE}/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == user["username"]
