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
ME_PASSWORD_URL = "/api/v1/users/me/password"
ME_USERNAME_URL = "/api/v1/users/me/username"
INTERNAL_API_KEY = "test-internal-api-key"

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

    @pytest.mark.asyncio()
    async def test_register_race_integrity_error_returns_409(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression test for the register check-then-insert race
        (finding 2): if a concurrent duplicate registration slips past
        the pre-checks and only trips the DB's unique constraint on
        insert, the API must still respond 409, not an unhandled 500.
        """
        from app.adapters.outbound.postgres_user_repository import (
            PostgresUserRepository,
        )
        from sqlalchemy.exc import IntegrityError

        async def _racing_create(self: PostgresUserRepository, *args: object, **kwargs: object) -> None:
            raise IntegrityError(
                "INSERT INTO users ...",
                {},
                Exception('duplicate key value violates unique constraint "ix_users_email"'),
            )

        monkeypatch.setattr(PostgresUserRepository, "create", _racing_create)

        resp = await client.post(REGISTER_URL, json=VALID_USER)

        assert resp.status_code == 409


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


# ── Profil-skrivninger (F2-08) ──────────────────────────────────────


async def _register_and_auth(client: AsyncClient) -> dict[str, str]:
    """Registrér VALID_USER, log ind, og returnér en Authorization-header."""
    await client.post(REGISTER_URL, json=VALID_USER)
    token_data = await _login(client, VALID_USER["email"], VALID_USER["password"])
    return {"Authorization": f"Bearer {token_data['access_token']}"}


class TestChangePassword:
    @pytest.mark.asyncio()
    async def test_change_password_persists_new_hash(self, client: AsyncClient) -> None:
        """204 alene beviser ingenting — ruten kunne svare 204 uden at
        skrive. Beviset er at det NYE password logger ind og det GAMLE
        afvises bagefter.
        """
        headers = await _register_and_auth(client)

        resp = await client.put(
            ME_PASSWORD_URL,
            json={"current_password": "secret1234", "new_password": "brandnew5678"},
            headers=headers,
        )
        assert resp.status_code == 204

        with_new = await client.post(
            LOGIN_URL,
            json={"username_or_email": VALID_USER["email"], "password": "brandnew5678"},
        )
        assert with_new.status_code == 200

        with_old = await client.post(
            LOGIN_URL,
            json={"username_or_email": VALID_USER["email"], "password": "secret1234"},
        )
        assert with_old.status_code == 401

    @pytest.mark.asyncio()
    async def test_wrong_current_password_is_403_never_401(self, client: AsyncClient) -> None:
        """Assertionen på ``!= 401`` ser overflødig ud ved siden af
        ``== 403``. Den er det ikke: den navngiver regressionen.

        Frontendens apiClient kalder ``handleUnauthorized()`` på enhver
        401 fra en ikke-auth-rute — den rydder auth-storage og redirecter
        til /login. Svarer denne rute 401, bliver konsekvensen af en
        tastefejl i "nuværende adgangskode" altså at brugeren logges ud,
        og fejlen ligner ikke sin årsag. Genbruges
        ``InvalidCredentialsException`` her ved en senere oprydning, er
        det denne linje der fanger det.
        """
        headers = await _register_and_auth(client)

        resp = await client.put(
            ME_PASSWORD_URL,
            json={"current_password": "wrong_password", "new_password": "brandnew5678"},
            headers=headers,
        )

        assert resp.status_code == 403
        assert resp.status_code != 401

    @pytest.mark.asyncio()
    async def test_wrong_current_password_leaves_password_unchanged(self, client: AsyncClient) -> None:
        headers = await _register_and_auth(client)

        await client.put(
            ME_PASSWORD_URL,
            json={"current_password": "wrong_password", "new_password": "brandnew5678"},
            headers=headers,
        )

        still_works = await client.post(
            LOGIN_URL,
            json={"username_or_email": VALID_USER["email"], "password": "secret1234"},
        )
        assert still_works.status_code == 200

    @pytest.mark.asyncio()
    async def test_change_password_requires_auth(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        resp = await client.put(
            ME_PASSWORD_URL,
            json={"current_password": "secret1234", "new_password": "brandnew5678"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_too_short_new_password_is_422(self, client: AsyncClient) -> None:
        headers = await _register_and_auth(client)

        resp = await client.put(
            ME_PASSWORD_URL,
            json={"current_password": "secret1234", "new_password": "kort"},
            headers=headers,
        )

        assert resp.status_code == 422


class TestChangeUsername:
    @pytest.mark.asyncio()
    async def test_change_username_reflected_in_get_me(self, client: AsyncClient) -> None:
        headers = await _register_and_auth(client)

        resp = await client.put(ME_USERNAME_URL, json={"username": "alice_ny"}, headers=headers)

        assert resp.status_code == 200
        assert resp.json()["username"] == "alice_ny"

        me = await client.get(ME_URL, headers=headers)
        assert me.json()["username"] == "alice_ny"

    @pytest.mark.asyncio()
    async def test_change_username_to_own_name_is_ok_not_conflict(self, client: AsyncClient) -> None:
        """Uændret navn må ikke give 409. Uden no-op'et i use casen ville
        unikhedstjekket finde brugeren selv og afvise gemmet.
        """
        headers = await _register_and_auth(client)

        resp = await client.put(ME_USERNAME_URL, json={"username": "alice"}, headers=headers)

        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    @pytest.mark.asyncio()
    async def test_change_username_to_taken_name_is_409(self, client: AsyncClient) -> None:
        headers = await _register_and_auth(client)
        await client.post(
            REGISTER_URL,
            json={"username": "bob", "email": "bob@example.com", "password": "secret1234"},
        )

        resp = await client.put(ME_USERNAME_URL, json={"username": "bob"}, headers=headers)

        assert resp.status_code == 409

    @pytest.mark.asyncio()
    async def test_change_username_requires_auth(self, client: AsyncClient) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        resp = await client.put(ME_USERNAME_URL, json={"username": "alice_ny"})

        assert resp.status_code == 401


class TestUpdatedAtStamp:
    """Migration 003's kolonne skal faktisk skrives.

    Uden disse to ville feltet være dekoration: alle ruterne svarer det
    samme uanset om ``updated_at`` sættes, så ingen anden test i filen
    kan se forskel på en kolonne der virker og en der aldrig røres.
    """

    @pytest.mark.asyncio()
    async def test_fresh_user_has_null_updated_at(self, client: AsyncClient, db_session: AsyncSession) -> None:
        await client.post(REGISTER_URL, json=VALID_USER)

        from app.models import UserModel

        result = await db_session.execute(select(UserModel))
        assert result.scalars().one().updated_at is None

    @pytest.mark.asyncio()
    async def test_username_change_stamps_updated_at(self, client: AsyncClient, db_session: AsyncSession) -> None:
        headers = await _register_and_auth(client)

        await client.put(ME_USERNAME_URL, json={"username": "alice_ny"}, headers=headers)

        from app.models import UserModel

        result = await db_session.execute(select(UserModel))
        user = result.scalars().one()
        await db_session.refresh(user)
        assert user.updated_at is not None


class TestInternalUserLookup:
    @pytest.mark.asyncio()
    async def test_get_user_by_id_rejects_missing_internal_api_key(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_API_KEY)
        registered = await _register(client)
        user_id = registered["response"].json()["id"]

        resp = await client.get(f"/api/v1/users/{user_id}")

        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_get_user_by_id_accepts_internal_api_key(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_API_KEY)
        registered = await _register(client)
        user_id = registered["response"].json()["id"]

        resp = await client.get(
            f"/api/v1/users/{user_id}",
            headers={"X-Internal-API-Key": INTERNAL_API_KEY},
        )

        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"


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
