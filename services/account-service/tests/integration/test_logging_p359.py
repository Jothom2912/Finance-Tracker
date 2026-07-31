"""P3-59: hvad account-service efterlader i loggen — og hvad den bevidst ikke gør.

Testene her er ikke "logger vi noget", men de tre påstande admissionsreglen står og falder
med:

1. hvert nyt kald har det rigtige **niveau** og **loggernavn** (en linje på den forkerte
   logger er præcis den tavse fejl P3-57 og dette item findes for at fange),
2. beskeden bærer den **diskriminerende værdi** — det tal eller id der gør linjen til en
   diagnose frem for en gentagelse af access-linjen,
3. de afvisninger reglen holder UDE logger stadig ingenting.

`account` er ikke på typecheck-gaten (P3-01/P3-39: intet ``pyproject.toml``), så disse
tests plus den live-drevne verifikation er hele dækningen af fase 4.  Det er den svageste
del af P3-59's verifikation og skal læses som sådan.
"""

import logging
from unittest.mock import patch

import httpx
import pytest
from app.adapters.outbound.user_adapter import UserServiceAdapter

from tests.conftest import _make_auth_header

ACCOUNT_API = "app.adapters.inbound.account_api"
INTERNAL_API = "app.adapters.inbound.internal_api"
SERVICE = "app.application.service"
USER_ADAPTER = "app.adapters.outbound.user_adapter"


def _records(caplog, logger_name: str, level: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == logger_name and r.levelno == level]


def _fake_response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body if json_body is not None else {},
        request=httpx.Request("GET", "http://mock-user-service:8001/api/v1/users/1"),
    )


def _create_account(client, user_id: int, name: str = "Konto") -> int:
    with patch.object(UserServiceAdapter, "exists", return_value=True):
        resp = client.post(
            "/api/v1/accounts/",
            json={"name": name, "saldo": 0},
            headers=_make_auth_header(user_id=user_id),
        )
    assert resp.status_code == 201
    return resp.json()["idAccount"]


# ---------------------------------------------------------------------------
# Ejerskabs-403'erne
# ---------------------------------------------------------------------------


class TestOwnershipRejections:
    def test_get_foreign_account_logs_warning_with_both_user_ids(self, client, caplog):
        account_id = _create_account(client, user_id=1, name="Ejers konto")

        with caplog.at_level(logging.DEBUG):
            resp = client.get(f"/api/v1/accounts/{account_id}", headers=_make_auth_header(user_id=2))

        assert resp.status_code == 403
        records = _records(caplog, ACCOUNT_API, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        # Begge parter skal stå på linjen: uden ejeren kan man ikke se om det var et
        # forældet konto-id fra en delt visning eller et opslag på en fremmed bruger.
        assert "2" in message and str(account_id) in message
        assert "1" in message

    def test_put_foreign_account_logs_its_own_line(self, client, caplog):
        account_id = _create_account(client, user_id=1)

        with caplog.at_level(logging.DEBUG):
            resp = client.put(
                f"/api/v1/accounts/{account_id}",
                json={"name": "hijack", "saldo": 0, "budget_start_day": 1},
                headers=_make_auth_header(user_id=2),
            )

        assert resp.status_code == 403
        records = _records(caplog, ACCOUNT_API, logging.WARNING)
        assert len(records) == 1
        # Skrivningen skal kunne skelnes fra læsningen i loggen, ikke kun i access-linjen.
        assert "opdatering" in records[0].getMessage().lower()

    def test_own_account_logs_nothing(self, client, caplog):
        account_id = _create_account(client, user_id=1)

        with caplog.at_level(logging.DEBUG):
            resp = client.get(f"/api/v1/accounts/{account_id}", headers=_make_auth_header(user_id=1))

        assert resp.status_code == 200
        assert _records(caplog, ACCOUNT_API, logging.WARNING) == []


# ---------------------------------------------------------------------------
# Negative kontroller — det reglen holder ude
# ---------------------------------------------------------------------------


class TestSilentByDesign:
    def test_ordinary_404_logs_nothing(self, client, caplog):
        with caplog.at_level(logging.DEBUG):
            resp = client.get("/api/v1/accounts/999999", headers=_make_auth_header(user_id=1))

        assert resp.status_code == 404
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    def test_422_logs_nothing(self, client, caplog):
        with caplog.at_level(logging.DEBUG):
            resp = client.post(
                "/api/v1/accounts/",
                json={"saldo": "ikke-et-tal"},
                headers=_make_auth_header(user_id=1),
            )

        assert resp.status_code == 422
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    def test_missing_internal_key_header_is_422_and_logs_nothing(self, client, caplog):
        """Step 1's fund, fastholdt som test.

        ``Header(...)`` er uden default, så Pydantic afviser før ``_verify_internal_key``
        kører.  Grenen "nøgle mangler helt" er altså uopnåelig, og hvis nogen senere giver
        headeren en default, falder denne test — ikke stille, men rødt.
        """
        with caplog.at_level(logging.DEBUG):
            resp = client.get("/api/v1/internal/accounts/1/exists")

        assert resp.status_code == 422
        assert _records(caplog, INTERNAL_API, logging.WARNING) == []
        assert _records(caplog, INTERNAL_API, logging.ERROR) == []

    def test_internal_404_logs_nothing(self, client, caplog):
        with patch(f"{INTERNAL_API}.INTERNAL_API_KEY", "korrekt-noegle"), caplog.at_level(logging.DEBUG):
            resp = client.get(
                "/api/v1/internal/accounts/999999/owner",
                headers={"x-internal-api-key": "korrekt-noegle"},
            )

        assert resp.status_code == 404
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ---------------------------------------------------------------------------
# Den interne nøgle — én 403, to årsager, to ejere
# ---------------------------------------------------------------------------


class TestInternalKey:
    def test_wrong_key_logs_warning_without_the_value(self, client, caplog):
        with patch(f"{INTERNAL_API}.INTERNAL_API_KEY", "korrekt-noegle"), caplog.at_level(logging.DEBUG):
            resp = client.get(
                "/api/v1/internal/accounts/1/exists",
                headers={"x-internal-api-key": "hemmelighed-fra-et-andet-miljoe"},
            )

        assert resp.status_code == 403
        records = _records(caplog, INTERNAL_API, logging.WARNING)
        assert len(records) == 1
        # En afvist nøgle kan være en GYLDIG nøgle fra et andet miljø. Hverken den sendte
        # eller den forventede værdi må havne i loggen.
        assert "hemmelighed-fra-et-andet-miljoe" not in records[0].getMessage()
        assert "korrekt-noegle" not in records[0].getMessage()
        assert _records(caplog, INTERNAL_API, logging.ERROR) == []

    def test_unconfigured_key_is_error_not_warning(self, client, caplog):
        with patch(f"{INTERNAL_API}.INTERNAL_API_KEY", None), caplog.at_level(logging.DEBUG):
            resp = client.get(
                "/api/v1/internal/accounts/1/exists",
                headers={"x-internal-api-key": "hvad-som-helst"},
            )

        assert resp.status_code == 403
        # `error`, fordi ejeren af fejlen er os: hver eneste interne request afvises, og
        # goal-services ejerskabstjek fejler konsistent. Niveauet ER påstanden her.
        assert len(_records(caplog, INTERNAL_API, logging.ERROR)) == 1
        assert _records(caplog, INTERNAL_API, logging.WARNING) == []

    def test_correct_key_logs_nothing(self, client, caplog):
        with patch(f"{INTERNAL_API}.INTERNAL_API_KEY", "korrekt-noegle"), caplog.at_level(logging.DEBUG):
            resp = client.get(
                "/api/v1/internal/accounts/1/exists",
                headers={"x-internal-api-key": "korrekt-noegle"},
            )

        assert resp.status_code == 200
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ---------------------------------------------------------------------------
# user_adapter — planens vigtigste enkeltlinje, og dens fravalg
# ---------------------------------------------------------------------------


class TestUserAdapter:
    @pytest.mark.parametrize("status_code", [401, 422, 500, 503])
    def test_non_404_failure_logs_status_code(self, caplog, status_code):
        adapter = UserServiceAdapter()

        with patch("httpx.get", return_value=_fake_response(status_code)), caplog.at_level(logging.DEBUG):
            result = adapter.exists(42)

        assert result is False
        records = _records(caplog, USER_ADAPTER, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        # Statuskoden ER diskriminanten: 401 = roteret nøgle, 503 = user-service syg.
        # Uden den er linjen kun "noget gik galt", hvilket 400'en allerede antydede.
        assert str(status_code) in message
        assert "42" in message

    def test_404_is_the_unambiguous_answer_and_logs_nothing(self, caplog):
        """Fravalget der gør de øvrige linjer brugbare.

        En 404 fra user-service betyder præcis hvad 400'en til klienten derefter siger.
        Loggede vi den, ville linjen fyre hver gang nogen taster et forkert bruger-id — og
        så drukner de fire statuskoder ovenfor der faktisk betyder noget.
        """
        adapter = UserServiceAdapter()

        with patch("httpx.get", return_value=_fake_response(404)), caplog.at_level(logging.DEBUG):
            result = adapter.exists(42)

        assert result is False
        assert _records(caplog, USER_ADAPTER, logging.WARNING) == []

    def test_200_logs_nothing(self, caplog):
        adapter = UserServiceAdapter()

        with patch("httpx.get", return_value=_fake_response(200, {"idUser": 42})), caplog.at_level(logging.DEBUG):
            assert adapter.exists(42) is True

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    def test_200_without_id_field_is_error(self, caplog):
        adapter = UserServiceAdapter()

        with (
            patch("httpx.get", return_value=_fake_response(200, {"username": "alice"})),
            caplog.at_level(logging.DEBUG),
        ):
            result = adapter.get_users_by_ids([42])

        assert result == []
        # `error`: user-service brød en kontrakt vi selv ejer. Ville ellers forsvinde ud i
        # et `InvalidUserInGroup` der ligner brugerens tastefejl.
        records = _records(caplog, USER_ADAPTER, logging.ERROR)
        assert len(records) == 1
        assert "42" in records[0].getMessage()

    def test_group_lookup_non_404_logs_warning(self, caplog):
        adapter = UserServiceAdapter()

        with patch("httpx.get", return_value=_fake_response(503)), caplog.at_level(logging.DEBUG):
            assert adapter.get_users_by_ids([7]) == []

        records = _records(caplog, USER_ADAPTER, logging.WARNING)
        assert len(records) == 1
        assert "503" in records[0].getMessage()

    def test_group_lookup_404_logs_nothing(self, caplog):
        adapter = UserServiceAdapter()

        with patch("httpx.get", return_value=_fake_response(404)), caplog.at_level(logging.DEBUG):
            assert adapter.get_users_by_ids([7]) == []

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ---------------------------------------------------------------------------
# Domænefejlene i application-laget
# ---------------------------------------------------------------------------


class TestDomainRejections:
    def test_unknown_user_from_valid_token_logs_warning(self, client, caplog):
        with patch.object(UserServiceAdapter, "exists", return_value=False), caplog.at_level(logging.DEBUG):
            resp = client.post(
                "/api/v1/accounts/",
                json={"name": "Konto", "saldo": 0},
                headers=_make_auth_header(user_id=999),
            )

        assert resp.status_code == 400
        records = _records(caplog, SERVICE, logging.WARNING)
        assert len(records) == 1
        assert "999" in records[0].getMessage()

    def test_invalid_group_users_logs_which_ids_were_unresolved(self, client, caplog):
        with (
            patch.object(UserServiceAdapter, "get_users_by_ids", return_value=[(1, "alice")]),
            caplog.at_level(logging.DEBUG),
        ):
            resp = client.post(
                "/api/v1/account-groups/",
                json={"name": "Ugyldig", "max_users": 5, "user_ids": [1, 999, 1000]},
                headers=_make_auth_header(user_id=1),
            )

        assert resp.status_code == 400
        # Bodyen siger kun "Mindst én bruger ID er ugyldig." — hele pointen med linjen er
        # at loggen siger *hvilke*.
        assert "Mindst én" in resp.json()["detail"]
        records = _records(caplog, SERVICE, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        assert "999" in message and "1000" in message

    def test_valid_group_logs_nothing(self, client, caplog):
        with (
            patch.object(UserServiceAdapter, "get_users_by_ids", return_value=[(1, "alice")]),
            caplog.at_level(logging.DEBUG),
        ):
            resp = client.post(
                "/api/v1/account-groups/",
                json={"name": "Familie", "max_users": 5, "user_ids": [1]},
                headers=_make_auth_header(user_id=1),
            )

        assert resp.status_code == 201
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
