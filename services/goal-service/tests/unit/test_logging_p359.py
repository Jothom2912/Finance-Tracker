"""P3-59: goal-services første loglinjer — og de fravalg der holder dem brugbare.

Servicen havde nul logging-statements i hele API-processen før dette item. Testene her
holder tre påstande fast:

1. **niveau og loggernavn** pr. kald — en linje på den forkerte logger findes ikke når man
   søger efter den, og er dermed lige så tavs som ingen linje,
2. **den diskriminerende værdi** står i beskeden — statuskoden, konto-id'et, ejeren,
3. de afvisninger admissionsreglen holder ude logger **stadig ingenting** — særligt den
   ordinære 404 på et mål der aldrig har eksisteret.

Den vigtigste her er 403/404-asymmetrien: samme krydsbruger-forsøg får to forskellige
statuskoder afhængigt af ruten, og 404-varianten var indtil nu ikke til at skelne fra en
helt almindelig "målet findes ikke".
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.adapters.outbound.account_adapter import AccountServiceAdapter
from app.application.dto import GoalBase, GoalCreate, GoalResponse
from app.application.service import GoalService
from app.auth import get_current_user_id
from app.domain.entities import Goal, GoalStatus
from app.domain.exceptions import NotAccountOwner, UpstreamServiceUnavailable

# `app.main` importeres på MODUL-niveau, ikke inde i testen — og det er ikke stilistisk.
# Modulet kalder `setup_logging()` ved import, som via `dictConfig` **erstatter** root's
# handlers.  Sker importen inde i en test, river den `caplog`s egen handler væk midt i
# målingen, og testen fejler med nul records mens linjen tydeligt står i stderr.  Præcis
# den sidste-skriver-vinder-mekanik P3-57 dokumenterede — her ramte den testen i stedet
# for produktionen.
from app.main import _parse_account_id, app
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

SERVICE_LOGGER = "app.application.service"
ADAPTER_LOGGER = "app.adapters.outbound.account_adapter"
MAIN_LOGGER = "app.main"

OWNER_USER_ID = 1
OTHER_USER_ID = 99
ACCOUNT_ID = 555
GOAL_ID = 10


def _records(caplog, logger_name: str, level: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == logger_name and r.levelno == level]


def _client_with_service(service) -> TestClient:
    from app.dependencies import get_goal_service

    app.dependency_overrides[get_goal_service] = lambda: service
    app.dependency_overrides[get_current_user_id] = lambda: OWNER_USER_ID
    return TestClient(app)


def _goal_response(**overrides) -> GoalResponse:
    defaults = dict(
        idGoal=GOAL_ID,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status=GoalStatus.ACTIVE,
        effective_status=GoalStatus.ACTIVE,
        progress_percent=20.0,
        Account_idAccount=ACCOUNT_ID,
    )
    defaults.update(overrides)
    return GoalResponse(**defaults)


def make_uow() -> MagicMock:
    uow = MagicMock()
    uow.goals = AsyncMock()
    uow.outbox = AsyncMock()
    uow.allocations = AsyncMock()
    uow.unallocated = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return uow


def _goal(**overrides) -> Goal:
    defaults = dict(
        id=GOAL_ID,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        account_id=ACCOUNT_ID,
    )
    defaults.update(overrides)
    return Goal(**defaults)


@pytest.fixture()
def uow() -> MagicMock:
    return make_uow()


@pytest.fixture()
def foreign_port() -> AsyncMock:
    """En konto-port hvor kontoen tilhører en ANDEN end den der spørger."""
    port = AsyncMock()
    port.get_owner_user_id.return_value = OWNER_USER_ID
    return port


@pytest.fixture()
def service(uow: MagicMock, foreign_port: AsyncMock) -> GoalService:
    return GoalService(uow=uow, account_port=foreign_port)


# ---------------------------------------------------------------------------
# 403/404-asymmetrien — itemets egentlige fund i denne service
# ---------------------------------------------------------------------------


class TestOwnershipAsymmetry:
    @pytest.mark.asyncio()
    async def test_403_path_names_the_status_code(self, service: GoalService, caplog) -> None:
        with caplog.at_level(logging.DEBUG), pytest.raises(NotAccountOwner):
            await service.list_goals(ACCOUNT_ID, OTHER_USER_ID)

        records = _records(caplog, SERVICE_LOGGER, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        # Statuskoden på linjen er det der gør den matchbar mod access-linjen ved siden af.
        assert "403" in message
        assert str(OTHER_USER_ID) in message and str(ACCOUNT_ID) in message and str(OWNER_USER_ID) in message

    @pytest.mark.asyncio()
    async def test_404_path_names_the_status_code_and_says_it_is_a_foreign_goal(
        self, service: GoalService, uow: MagicMock, caplog
    ) -> None:
        uow.goals.get_by_id.return_value = _goal()

        with caplog.at_level(logging.DEBUG):
            result = await service.get_goal(GOAL_ID, OTHER_USER_ID)

        # Adfærden er UÆNDRET: stadig None → 404, stadig ingen bekræftelse til klienten
        # af at målet findes. Kun loggen ved forskellen.
        assert result is None
        records = _records(caplog, SERVICE_LOGGER, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        assert "404" in message
        assert str(GOAL_ID) in message and str(OWNER_USER_ID) in message

    @pytest.mark.asyncio()
    async def test_missing_goal_is_an_ordinary_404_and_logs_nothing(
        self, service: GoalService, uow: MagicMock, caplog
    ) -> None:
        """Fravalget der gør de seks linjer ovenfor værd at have.

        Findes målet ikke, er 404'en entydig og der er intet tab. Loggede vi den, ville
        signalet "nogen rører et mål der ikke er deres" drukne i almindelige forældede id'er.
        """
        uow.goals.get_by_id.return_value = None

        with caplog.at_level(logging.DEBUG):
            assert await service.get_goal(GOAL_ID, OTHER_USER_ID) is None

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    @pytest.mark.asyncio()
    async def test_owner_access_logs_nothing(self, service: GoalService, uow: MagicMock, caplog) -> None:
        uow.goals.get_by_id.return_value = _goal()

        with caplog.at_level(logging.DEBUG):
            assert await service.get_goal(GOAL_ID, OWNER_USER_ID) is not None

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        ("call", "expected_word"),
        [
            (lambda s: s.get_goal(GOAL_ID, OTHER_USER_ID), "læsning"),
            (
                lambda s: s.update_goal(
                    GOAL_ID,
                    GoalBase(
                        name="x",
                        target_amount=1,
                        current_amount=0,
                        target_date=None,
                        status="active",
                    ),
                    OTHER_USER_ID,
                ),
                "opdatering",
            ),
            (lambda s: s.delete_goal(GOAL_ID, OTHER_USER_ID), "sletning"),
            (lambda s: s.set_default_goal(GOAL_ID, OTHER_USER_ID), "sæt-default"),
            (lambda s: s.clear_default_goal(GOAL_ID, OTHER_USER_ID), "ryd-default"),
            (lambda s: s.get_allocation_history(GOAL_ID, OTHER_USER_ID), "historik-opslag"),
        ],
    )
    async def test_all_six_denial_paths_log_and_name_the_operation(
        self, service: GoalService, uow: MagicMock, caplog, call, expected_word
    ) -> None:
        """Alle seks ``return None``-stier, hver med sin egen ordlyd.

        Grunden til at operationen står på linjen: en afvist *sletning* af en andens mål er
        et andet signal end en afvist *læsning*, og de deler statuskode.
        """
        uow.goals.get_by_id.return_value = _goal()

        with caplog.at_level(logging.DEBUG):
            await call(service)

        records = _records(caplog, SERVICE_LOGGER, logging.WARNING)
        assert len(records) == 1
        assert expected_word in records[0].getMessage()


# ---------------------------------------------------------------------------
# account_adapter — de to metoder der håndterer samme fejl på modsat vis
# ---------------------------------------------------------------------------


class _FakeAsyncClient:
    def __init__(self, response: httpx.Response | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def __call__(self, *args, **kwargs):  # httpx.AsyncClient(timeout=...)
        return self

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def get(self, url: str, headers: dict | None = None) -> httpx.Response:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _response(status_code: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=body if body is not None else {},
        request=httpx.Request("GET", "http://account-service:8003/x"),
    )


def _adapter() -> AccountServiceAdapter:
    return AccountServiceAdapter(base_url="http://account-service:8003", api_key="k", timeout=1.0)


class TestAccountAdapterOwner:
    @pytest.mark.asyncio()
    async def test_request_error_logs_before_raising_503(self, caplog) -> None:
        fake = _FakeAsyncClient(error=httpx.ReadTimeout("timed out"))

        with (
            patch(f"{ADAPTER_LOGGER}.httpx.AsyncClient", fake),
            caplog.at_level(logging.DEBUG),
            pytest.raises(UpstreamServiceUnavailable),
        ):
            await _adapter().get_owner_user_id(ACCOUNT_ID)

        records = _records(caplog, ADAPTER_LOGGER, logging.WARNING)
        assert len(records) == 1
        # 503'en bærer kun "account-service is unavailable". Diskriminanten findes kun her.
        assert "ReadTimeout" in records[0].getMessage()

    @pytest.mark.asyncio()
    async def test_non_200_logs_the_status_code_before_raising_503(self, caplog) -> None:
        """Samme 503 udad, helt anden årsag: servicen svarede, bare uden noget vi kan bruge."""
        fake = _FakeAsyncClient(response=_response(403))

        with (
            patch(f"{ADAPTER_LOGGER}.httpx.AsyncClient", fake),
            caplog.at_level(logging.DEBUG),
            pytest.raises(UpstreamServiceUnavailable),
        ):
            await _adapter().get_owner_user_id(ACCOUNT_ID)

        records = _records(caplog, ADAPTER_LOGGER, logging.WARNING)
        assert len(records) == 1
        assert "403" in records[0].getMessage()

    @pytest.mark.asyncio()
    async def test_404_is_unambiguous_and_logs_nothing(self, caplog) -> None:
        """Fravalg: 400'en navngiver allerede kontoen, og et forældet id er almindelig brug."""
        from app.domain.exceptions import AccountNotFoundForGoal

        fake = _FakeAsyncClient(response=_response(404))

        with (
            patch(f"{ADAPTER_LOGGER}.httpx.AsyncClient", fake),
            caplog.at_level(logging.DEBUG),
            pytest.raises(AccountNotFoundForGoal),
        ):
            await _adapter().get_owner_user_id(ACCOUNT_ID)

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    @pytest.mark.asyncio()
    async def test_successful_lookup_logs_nothing(self, caplog) -> None:
        fake = _FakeAsyncClient(response=_response(200, {"user_id": OWNER_USER_ID}))

        with patch(f"{ADAPTER_LOGGER}.httpx.AsyncClient", fake), caplog.at_level(logging.DEBUG):
            assert await _adapter().get_owner_user_id(ACCOUNT_ID) == OWNER_USER_ID

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ---------------------------------------------------------------------------
# main.py — headeren og race'en
# ---------------------------------------------------------------------------


class TestHeaderAndRace:
    def test_non_integer_account_header_logs_the_value(self, caplog) -> None:
        with caplog.at_level(logging.DEBUG), pytest.raises(Exception):
            _parse_account_id("abc")

        records = _records(caplog, MAIN_LOGGER, logging.WARNING)
        assert len(records) == 1
        assert "abc" in records[0].getMessage()

    def test_long_header_value_is_truncated(self, caplog) -> None:
        """Værdien er hele signalet, men den er også fremmed input.

        64 tegn er nok til at genkende hvad nogen prøvede; en ubegrænset værdi ville lade
        en klient bestemme hvor lang vores loglinje er.
        """
        with caplog.at_level(logging.DEBUG), pytest.raises(Exception):
            _parse_account_id("A" * 5000)

        records = _records(caplog, MAIN_LOGGER, logging.WARNING)
        assert len(records) == 1
        assert len(records[0].getMessage()) < 200

    def test_valid_header_logs_nothing(self, caplog) -> None:
        with caplog.at_level(logging.DEBUG):
            assert _parse_account_id("511") == 511

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    def test_lost_default_goal_race_logs_goal_and_user(self, caplog) -> None:
        """409'en fra det partielle unique index fyrer gennem ruten, ikke gennem servicen.

        Testen går derfor gennem `TestClient`: `IntegrityError` skal kastes af den
        overridede service, så `except`-grenen i ruten er den der kører.  Uden dette
        var racen det ene nye kald i fase 5 uden en test — og den er samtidig den eneste
        der ikke kan drives fra en enkelt request, fordi den kræver to samtidige.
        """
        service = MagicMock()
        service.set_default_goal = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("duplicate key")))

        with caplog.at_level(logging.DEBUG):
            client = _client_with_service(service)
            try:
                response = client.put(f"/api/v1/goals/{GOAL_ID}/default")
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 409
        records = _records(caplog, MAIN_LOGGER, logging.WARNING)
        assert len(records) == 1
        message = records[0].getMessage()
        assert str(GOAL_ID) in message
        assert str(OWNER_USER_ID) in message

    def test_successful_set_default_logs_nothing(self, caplog) -> None:
        """Negativ kontrol: den lykkelige sti er en gennemført tilstandsændring.

        Reglen giver den ingen linje — access-linjen siger allerede `200 PUT
        /goals/10/default`, og en `info` her ville være netop den duplikering
        admissionsreglen afviser.
        """
        service = MagicMock()
        service.set_default_goal = AsyncMock(return_value=_goal_response())

        with caplog.at_level(logging.DEBUG):
            client = _client_with_service(service)
            try:
                response = client.put(f"/api/v1/goals/{GOAL_ID}/default")
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ---------------------------------------------------------------------------
# create_goal: de to upstream-veje ind, og hvilken der er tavs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_create_goal_on_foreign_account_logs_the_403_line(service: GoalService, caplog) -> None:
    with caplog.at_level(logging.DEBUG), pytest.raises(NotAccountOwner):
        await service.create_goal(
            GoalCreate(
                name="Vacation",
                target_amount=5000,
                current_amount=1000,
                target_date=None,
                status="active",
                Account_idAccount=ACCOUNT_ID,
            ),
            user_id=OTHER_USER_ID,
        )

    records = _records(caplog, SERVICE_LOGGER, logging.WARNING)
    assert len(records) == 1
    assert "403" in records[0].getMessage()
