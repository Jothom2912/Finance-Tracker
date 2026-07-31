from __future__ import annotations

import json
import logging
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


# ── Logning i request-stien (P3-59) ──────────────────────────────


class TestRequestPathLogging:
    """P3-59: user-service havde 0 loglinjer i request-stien.

    Testene her er lige så meget om de afvisninger der IKKE må logge. Admissionsreglen er
    "en afvisning fortjener en linje hvis og kun hvis statuskoden alene er tvetydig om
    årsagen", og efter P3-57 bærer hver request allerede en access-linje. Uden de negative
    tests kan reglen eroderes til "log alle afvisninger", og så har vi bygget en anden
    access-log oven på den vi lige fik.
    """

    @pytest.mark.asyncio()
    async def test_failed_login_logs_warning(self, client: AsyncClient, caplog) -> None:
        await _register(client)

        with caplog.at_level(logging.WARNING, logger="app.main"):
            resp = await client.post(
                LOGIN_URL,
                json={"username_or_email": "alice", "password": "wrong-password"},
            )

        assert resp.status_code == 401
        records = [r for r in caplog.records if r.name == "app.main"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert LOGIN_URL in records[0].getMessage()

    @pytest.mark.asyncio()
    async def test_failed_login_never_logs_the_submitted_identifier(self, client: AsyncClient, caplog) -> None:
        """Brugere taster regelmæssigt deres password i brugernavnsfeltet."""
        with caplog.at_level(logging.WARNING, logger="app.main"):
            await client.post(
                LOGIN_URL,
                json={"username_or_email": "MitHemmeligePassword1", "password": "x"},
            )

        for record in caplog.records:
            assert "MitHemmeligePassword1" not in record.getMessage()

    @pytest.mark.asyncio()
    async def test_wrong_current_password_logs_warning(self, client: AsyncClient, caplog) -> None:
        await _register(client)
        token = (await _login(client, "alice", "secret1234"))["access_token"]

        with caplog.at_level(logging.WARNING, logger="app.main"):
            resp = await client.put(
                ME_PASSWORD_URL,
                json={"current_password": "not-it", "new_password": "brandnew1234"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 403
        assert [r for r in caplog.records if r.name == "app.main"]

    @pytest.mark.asyncio()
    async def test_duplicate_registration_does_not_log(self, client: AsyncClient, caplog) -> None:
        """FRAVALG: en 409 på et taget brugernavn er en almindelig bruger, og bodyen siger
        allerede hvilket felt der kolliderede. En linje her duplikerer access-linjen."""
        await _register(client)

        with caplog.at_level(logging.DEBUG, logger="app.main"):
            resp = await _register(client)

        assert resp["response"].status_code == 409
        assert [r for r in caplog.records if r.name == "app.main"] == []

    @pytest.mark.asyncio()
    async def test_internal_lookup_of_unknown_user_does_not_log(
        self, client: AsyncClient, caplog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FRAVALG: den interne rutes 404 er ENTYDIG, og den er desuden hvordan
        account-service' exists() normalt svarer nej — en linje ville fyre ved helt
        almindelig brug."""
        from app.config import settings

        monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_API_KEY)

        with caplog.at_level(logging.DEBUG, logger="app.main"):
            resp = await client.get(
                "/api/v1/users/999999",
                headers={"X-Internal-API-Key": INTERNAL_API_KEY},
            )

        assert resp.status_code == 404
        assert [r for r in caplog.records if r.name == "app.main"] == []

    @pytest.mark.asyncio()
    async def test_me_for_deleted_user_logs_warning(
        self, client: AsyncClient, db_session: AsyncSession, caplog
    ) -> None:
        """Modstykket til testen ovenfor: SAMME exception, men fra /me er den tvetydig —
        tokenet var gyldigt, så brugeren forsvandt under en levende session."""
        from app.models import UserModel

        await _register(client)
        token = (await _login(client, "alice", "secret1234"))["access_token"]
        user = (await db_session.execute(select(UserModel))).scalars().one()
        await db_session.delete(user)
        await db_session.commit()

        with caplog.at_level(logging.WARNING, logger="app.main"):
            resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 404
        records = [r for r in caplog.records if r.name == "app.main"]
        assert len(records) == 1
        assert "/me" in records[0].getMessage()

    @pytest.mark.asyncio()
    async def test_wrong_internal_api_key_logs_which_branch(
        self, client: AsyncClient, caplog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_API_KEY)
        logger_name = "app.adapters.inbound.rest_api"

        with caplog.at_level(logging.WARNING, logger=logger_name):
            resp = await client.get(
                "/api/v1/users/1",
                headers={"X-Internal-API-Key": "wrong-key"},
            )

        assert resp.status_code == 401
        message = next(r for r in caplog.records if r.name == logger_name).getMessage()
        assert "matcher ikke" in message
        # Aldrig hvad der blev sendt.
        assert "wrong-key" not in message

    @pytest.mark.asyncio()
    async def test_missing_internal_api_key_logs_a_different_branch(
        self, client: AsyncClient, caplog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hele pointen er at skelne de to, så de skal give to forskellige beskeder."""
        from app.config import settings

        monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_API_KEY)
        logger_name = "app.adapters.inbound.rest_api"

        with caplog.at_level(logging.WARNING, logger=logger_name):
            resp = await client.get("/api/v1/users/1")

        assert resp.status_code == 401
        message = next(r for r in caplog.records if r.name == logger_name).getMessage()
        assert "header mangler" in message

    @pytest.mark.asyncio()
    async def test_unconfigured_internal_api_key_logs_error(
        self, client: AsyncClient, caplog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ERROR, ikke WARNING: en deployment uden en påkrævet variabel er vores fejl.

        Det er også den fejl der hos account-service bliver en 400 'Bruger findes ikke'.
        """
        from app.config import settings

        monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
        logger_name = "app.adapters.inbound.rest_api"

        with caplog.at_level(logging.WARNING, logger=logger_name):
            resp = await client.get("/api/v1/users/1")

        assert resp.status_code == 503
        record = next(r for r in caplog.records if r.name == logger_name)
        assert record.levelno == logging.ERROR
        assert "INTERNAL_API_KEY" in record.getMessage()

    @pytest.mark.asyncio()
    async def test_toctou_on_write_logs_warning_without_values(
        self, client: AsyncClient, db_session: AsyncSession, caplog
    ) -> None:
        """rowcount == 0: brugeren fandtes ved use casens opslag, men ikke ved skrivningen.

        Feltnavnene må stå på linjen, værdierne ikke — `values` bærer password-hashet.
        """
        from app.adapters.outbound.postgres_user_repository import PostgresUserRepository
        from app.domain.exceptions import UserNotFoundException

        repo = PostgresUserRepository(db_session)
        logger_name = "app.adapters.outbound.postgres_user_repository"

        with caplog.at_level(logging.WARNING, logger=logger_name):
            with pytest.raises(UserNotFoundException):
                await repo.update_password(999999, "hash-der-aldrig-skrives")

        record = next(r for r in caplog.records if r.name == logger_name)
        assert record.levelno == logging.WARNING
        assert "999999" in record.getMessage()
        assert "hash-der-aldrig-skrives" not in record.getMessage()
