from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

REGISTER_URL = "/api/v1/users/register"
LOGIN_URL = "/api/v1/users/login"
ME_URL = "/api/v1/users/me"

VALID_USER = {
    "username": "alice",
    "email": "alice@example.com",
    "password": "secret1234",
}


async def _register(client: AsyncClient, **overrides: str) -> dict:
    payload = {**VALID_USER, **overrides}
    resp = await client.post(REGISTER_URL, json=payload)
    return {"response": resp, "payload": payload}


async def _login(client: AsyncClient, username_or_email: str, password: str) -> dict:
    resp = await client.post(LOGIN_URL, json={"username_or_email": username_or_email, "password": password})
    return resp.json()


# ── Registration ────────────────────────────────────────────────────


class TestRegister:
    @pytest.mark.asyncio()
    async def test_register_success(self, client: AsyncClient) -> None:
        resp = await client.post(REGISTER_URL, json=VALID_USER)

        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "alice"
        assert data["email"] == "alice@example.com"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio()
    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        duplicate = {**VALID_USER, "username": "bob"}
        resp = await client.post(REGISTER_URL, json=duplicate)

        assert resp.status_code == 409

    @pytest.mark.asyncio()
    async def test_register_duplicate_username(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        duplicate = {**VALID_USER, "email": "bob@example.com"}
        resp = await client.post(REGISTER_URL, json=duplicate)

        assert resp.status_code == 409

    @pytest.mark.asyncio()
    async def test_register_writes_outbox_event(self, client: AsyncClient, db_session: AsyncSession) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        from app.models import OutboxEventModel

        result = await db_session.execute(select(OutboxEventModel))
        entries = result.scalars().all()

        assert len(entries) == 1
        entry = entries[0]
        assert entry.event_type == "user.created"
        assert entry.aggregate_type == "user"
        assert entry.status == "pending"

        payload = json.loads(entry.payload_json)
        assert payload["email"] == "alice@example.com"
        assert payload["username"] == "alice"


# ── Login ───────────────────────────────────────────────────────────


class TestLogin:
    @pytest.mark.asyncio()
    async def test_login_success_with_email(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        resp = await client.post(
            LOGIN_URL,
            json={"username_or_email": "alice@example.com", "password": "secret1234"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] >= 1
        assert data["username"] == "alice"

    @pytest.mark.asyncio()
    async def test_login_success_with_username(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        resp = await client.post(
            LOGIN_URL,
            json={"username_or_email": "alice", "password": "secret1234"},
        )

        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    @pytest.mark.asyncio()
    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        resp = await client.post(
            LOGIN_URL,
            json={"username_or_email": "alice@example.com", "password": "wrongpass"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        resp = await client.post(
            LOGIN_URL,
            json={"username_or_email": "nobody@example.com", "password": "secret1234"},
        )

        assert resp.status_code == 401


# ── Get me ──────────────────────────────────────────────────────────


class TestGetMe:
    @pytest.mark.asyncio()
    async def test_get_me_authenticated(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)
        token_data = await _login(client, "alice@example.com", "secret1234")
        token = token_data["access_token"]

        resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "alice"
        assert data["email"] == "alice@example.com"

    @pytest.mark.asyncio()
    async def test_get_me_no_token(self, client: AsyncClient) -> None:
        resp = await client.get(ME_URL)

        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_get_me_invalid_token(self, client: AsyncClient) -> None:
        resp = await client.get(ME_URL, headers={"Authorization": "Bearer garbage.token.here"})

        assert resp.status_code == 401


# ── Cross-service JWT compatibility ──────────────────────────────


class TestCrossServiceJWT:
    @pytest.mark.asyncio()
    async def test_monolith_format_token_accepted(self, client: AsyncClient) -> None:
        """A token using the monolith payload format (user_id claim)
        must be accepted by user-service.
        """
        await client.post(REGISTER_URL, json=VALID_USER)
        from app.config import settings

        monolith_token = jwt.encode(
            {
                "user_id": 1,
                "username": "alice",
                "email": "alice@example.com",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

        resp = await client.get(
            ME_URL,
            headers={"Authorization": f"Bearer {monolith_token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    @pytest.mark.asyncio()
    async def test_user_service_token_contains_monolith_claims(self, client: AsyncClient) -> None:
        """Tokens issued by user-service must include user_id, username,
        and email claims so the monolith can decode them without changes.
        """
        await client.post(REGISTER_URL, json=VALID_USER)
        from app.config import settings

        login_resp = await client.post(
            LOGIN_URL,
            json={"username_or_email": "alice@example.com", "password": "secret1234"},
        )
        token = login_resp.json()["access_token"]

        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert payload["sub"] == str(payload["user_id"])
        assert payload["username"] == "alice"
        assert payload["email"] == "alice@example.com"
