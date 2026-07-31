"""P3-59: saga-services 403 siger nu hvilken af sine tre årsager der ramte.

`GET /api/v1/sagas/{id}` svarer `403 "Access denied"` i tre forskellige situationer, og de
kræver modsatte handlinger:

1. sagaen har **intet** `user_id` i sin kontekst — den er utilgængelig for alle, altså en
   bug hos den der startede den,
2. `user_id` er der, men er ikke et heltal — korrupt kontekst,
3. et ægte **krydstenant**-forsøg.

De to første er data-integritetssignaler, den tredje er et sikkerhedssignal. Uden en linje
er de ikke til at skelne — hverken fra hinanden eller fra et probe. Testene her holder fast
at hver gren får sin egen ordlyd, at værdien kun logges dér hvor den er signalet, og at den
ordinære 404 stadig er tavs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from app.adapters.outbound.postgres_saga_repository import PostgresSagaRepository
from app.config import settings
from app.domain.entities import SagaInstance, SagaStatus, SagaStep, StepStatus
from app.main import app
from fastapi.testclient import TestClient
from jose import jwt

MAIN_LOGGER = "app.main"

SAGA_ID = "saga-p359"
OWNER_USER_ID = 1
OTHER_USER_ID = 2


def _auth_header(user_id: int) -> dict[str, str]:
    token = jwt.encode(
        {
            "user_id": user_id,
            "username": "p359",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _records(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == MAIN_LOGGER and r.levelno == level]


def _saga_with_context(context: dict[str, Any] | None) -> SagaInstance:
    return SagaInstance(
        id=SAGA_ID,
        saga_type="bank_sync",
        correlation_id=SAGA_ID,
        current_step=0,
        status=SagaStatus.COMPLETED,
        context=context,
        steps=[SagaStep(index=0, name="fetch_transactions", status=StepStatus.SUCCEEDED)],
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )


def _client(monkeypatch: pytest.MonkeyPatch, saga: SagaInstance | None) -> TestClient:
    async def fake_get_by_id(self: PostgresSagaRepository, saga_id: str) -> SagaInstance | None:
        return saga if saga is not None and saga_id == SAGA_ID else None

    async def fake_get_by_correlation_id(self: PostgresSagaRepository, correlation_id: str) -> SagaInstance | None:
        return None

    monkeypatch.setattr(PostgresSagaRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresSagaRepository, "get_by_correlation_id", fake_get_by_correlation_id)
    return TestClient(app)


class TestThreeCausesOneStatusCode:
    def test_missing_user_id_says_the_saga_is_unreachable_for_everyone(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = _client(monkeypatch, _saga_with_context({"connection_id": "conn-1"}))

        with caplog.at_level(logging.DEBUG):
            response = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=_auth_header(OWNER_USER_ID))

        assert response.status_code == 403
        records = _records(caplog, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        assert "intet user_id" in message
        assert SAGA_ID in message

    def test_corrupt_user_id_logs_the_value_because_it_is_the_signal(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """En liste hvor et heltal var forventet — værdien er hele diagnosen.

        Den er samtidig sikker at logge: den kommer fra vores egen saga-kontekst, ikke fra
        requesten, og `_sanitize_context` holder allerede payload-nøglerne ude af svaret.
        """
        client = _client(monkeypatch, _saga_with_context({"user_id": ["1", "2"]}))

        with caplog.at_level(logging.DEBUG):
            response = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=_auth_header(OWNER_USER_ID))

        assert response.status_code == 403
        records = _records(caplog, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        assert "korrupt" in message
        assert "['1', '2']" in message

    def test_cross_tenant_names_owner_and_caller(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = _client(monkeypatch, _saga_with_context({"user_id": OWNER_USER_ID}))

        with caplog.at_level(logging.DEBUG):
            response = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=_auth_header(OTHER_USER_ID))

        assert response.status_code == 403
        records = _records(caplog, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        assert str(OTHER_USER_ID) in message and str(OWNER_USER_ID) in message
        # Den skal kunne skelnes fra de to data-integritetsgrene, ikke kun være en linje.
        assert "korrupt" not in message and "intet user_id" not in message

    def test_the_three_branches_do_not_share_wording(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Hele pointen med fase 6 for denne service, som én påstand.

        Sammenligningen er på **format-strengen** (`record.msg`), ikke på den formaterede
        besked. Første version brugte `getMessage()`, og den er upræcis på en måde der kan
        blive en falsk grøn: to grene kan dele ordlyd og alligevel give forskellige
        beskeder, fordi de interpolerede værdier (saga-id, bruger-id) er forskellige.
        Krydstenant-grenen er den udsatte — den er den eneste her der kaldes med et andet
        bruger-id. `record.msg` udtrykker den påstand jeg faktisk mener: tre grene, tre
        ordlyd, uafhængigt af hvad der interpoleres ind.

        Mutations-verificeret: kollapses den korrupte gren til samme ordlyd som den
        manglende, bliver den her rød.
        """
        templates = []
        for context, caller in (
            ({"connection_id": "c"}, OWNER_USER_ID),
            ({"user_id": "not-a-number"}, OWNER_USER_ID),
            ({"user_id": OWNER_USER_ID}, OTHER_USER_ID),
        ):
            caplog.clear()
            client = _client(monkeypatch, _saga_with_context(context))
            with caplog.at_level(logging.DEBUG):
                assert client.get(f"/api/v1/sagas/{SAGA_ID}", headers=_auth_header(caller)).status_code == 403
            templates.append(_records(caplog, logging.WARNING)[0].msg)

        assert len(set(templates)) == 3


class TestNegativeControls:
    def test_unknown_saga_is_an_ordinary_404_and_logs_nothing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Fravalget der holder 403-linjerne brugbare.

        En saga-id der ikke findes er entydig: 404'en siger præcis det. Loggede vi den,
        ville de tre 403-signaler drukne i almindelige forældede id'er.
        """
        client = _client(monkeypatch, None)

        with caplog.at_level(logging.DEBUG):
            response = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=_auth_header(OWNER_USER_ID))

        assert response.status_code == 404
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    def test_owner_access_logs_nothing(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        client = _client(monkeypatch, _saga_with_context({"user_id": OWNER_USER_ID}))

        with caplog.at_level(logging.DEBUG):
            response = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=_auth_header(OWNER_USER_ID))

        assert response.status_code == 200
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    def test_empty_context_is_the_missing_user_id_branch_not_a_crash(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """`context=None` er en reel tilstand i DB'en, ikke kun en typemulighed."""
        client = _client(monkeypatch, _saga_with_context(None))

        with caplog.at_level(logging.DEBUG):
            response = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=_auth_header(OWNER_USER_ID))

        assert response.status_code == 403
        assert "intet user_id" in _records(caplog, logging.WARNING)[0].getMessage()
