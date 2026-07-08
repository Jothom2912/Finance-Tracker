"""Integration tests for monthly-budgets REST API.

Tester to sikkerhedsregressioner end-to-end mod en rigtig PostgreSQL:
1. IDOR: en autentificeret bruger kan IKKE læse/ændre/slette/lukke en anden
   brugers månedsbudget (404 / null — ikke 403, for at undgå existence leaks).
2. Fail-closed month close: hvis transaction-service er utilgængelig returnerer
   POST /close 503, måneden lukkes IKKE og der skrives INGEN outbox-event.

Kræver Docker kørende.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_JWT_SECRET = "test-secret"
_JWT_ALGORITHM = "HS256"


def _make_token(user_id: int = 1) -> str:
    return jwt.encode({"sub": str(user_id), "user_id": user_id}, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def _migrated_db(postgres):
    sync_url = postgres.get_connection_url()
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")

    os.environ["DATABASE_URL"] = async_url
    os.environ["JWT_SECRET"] = _JWT_SECRET

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="module")
def async_db_url(postgres, _migrated_db):
    sync_url = postgres.get_connection_url()
    return sync_url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")


def _pg_execute(postgres, sql: str):
    """Kør SQL synkront via psycopg2 (undgår event-loop konflikter)."""
    import psycopg2

    raw_url = postgres.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    conn = psycopg2.connect(raw_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall() if cur.description else None
    cur.close()
    conn.close()
    return rows


@pytest.fixture(autouse=True)
def clean_db(postgres, _migrated_db):
    _pg_execute(postgres, "DELETE FROM budget_lines")
    _pg_execute(postgres, "DELETE FROM monthly_budgets")
    _pg_execute(postgres, "DELETE FROM outbox_events")


@pytest.fixture()
def mock_transaction_port():
    from app.application.ports.outbound import ITransactionPort

    port = AsyncMock(spec=ITransactionPort)
    port.get_expenses_by_category.return_value = {}
    return port


@pytest.fixture()
def client(async_db_url, mock_transaction_port):
    from app.application.monthly_budget_service import MonthlyBudgetService
    from app.application.ports.outbound import ICategoryPort
    from app.dependencies import get_monthly_budget_service
    from app.main import app

    mock_category_port = AsyncMock(spec=ICategoryPort)
    mock_category_port.exists.return_value = True
    mock_category_port.get_all_names.return_value = {1: "Mad"}

    _url = async_db_url

    async def override_get_monthly_budget_service():
        from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork

        engine = create_async_engine(_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            uow = SQLAlchemyUnitOfWork(session)
            yield MonthlyBudgetService(
                uow=uow,
                transaction_port=mock_transaction_port,
                category_port=mock_category_port,
            )
        await engine.dispose()

    app.dependency_overrides[get_monthly_budget_service] = override_get_monthly_budget_service

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def user1_headers():
    return {"Authorization": f"Bearer {_make_token(user_id=1)}"}


@pytest.fixture()
def user2_headers():
    return {"Authorization": f"Bearer {_make_token(user_id=2)}"}


def _create_budget(client, headers, account_id=1, month=6, year=2026):
    response = client.post(
        "/api/v1/monthly-budgets/",
        params={"account_id": account_id},
        json={"month": month, "year": year, "lines": [{"category_id": 1, "amount": 1000.0}]},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Tests: IDOR — kun ejeren har adgang til sit månedsbudget
# ---------------------------------------------------------------------------


class TestOwnershipEnforcement:
    def test_owner_can_read_own_budget(self, client, user1_headers) -> None:
        _create_budget(client, user1_headers)
        response = client.get(
            "/api/v1/monthly-budgets/",
            params={"account_id": 1, "month": 6, "year": 2026},
            headers=user1_headers,
        )
        assert response.status_code == 200
        assert response.json() is not None

    def test_other_user_cannot_read_budget(self, client, user1_headers, user2_headers) -> None:
        _create_budget(client, user1_headers)
        response = client.get(
            "/api/v1/monthly-budgets/",
            params={"account_id": 1, "month": 6, "year": 2026},
            headers=user2_headers,
        )
        assert response.status_code == 200
        assert response.json() is None

    def test_other_user_cannot_update_budget(self, client, user1_headers, user2_headers) -> None:
        created = _create_budget(client, user1_headers)
        response = client.put(
            f"/api/v1/monthly-budgets/{created['id']}",
            params={"account_id": 1},
            json={"lines": [{"category_id": 1, "amount": 1.0}]},
            headers=user2_headers,
        )
        assert response.status_code == 404

    def test_other_user_cannot_delete_budget(self, client, user1_headers, user2_headers) -> None:
        created = _create_budget(client, user1_headers)
        response = client.delete(
            f"/api/v1/monthly-budgets/{created['id']}",
            params={"account_id": 1},
            headers=user2_headers,
        )
        assert response.status_code == 404

        # Budgettet findes stadig for ejeren
        response = client.get(
            "/api/v1/monthly-budgets/",
            params={"account_id": 1, "month": 6, "year": 2026},
            headers=user1_headers,
        )
        assert response.json() is not None

    def test_other_user_cannot_close_budget(self, client, user1_headers, user2_headers, postgres) -> None:
        _create_budget(client, user1_headers)
        response = client.post(
            "/api/v1/monthly-budgets/close",
            params={"account_id": 1, "month": 6, "year": 2026},
            headers=user2_headers,
        )
        assert response.status_code == 404

        rows = _pg_execute(postgres, "SELECT closed_at FROM monthly_budgets")
        assert rows[0][0] is None
        assert _pg_execute(postgres, "SELECT id FROM outbox_events") == []

    def test_other_user_cannot_copy_budget(self, client, user1_headers, user2_headers) -> None:
        _create_budget(client, user1_headers)
        response = client.post(
            "/api/v1/monthly-budgets/copy",
            params={"account_id": 1},
            json={"source_month": 6, "source_year": 2026, "target_month": 7, "target_year": 2026},
            headers=user2_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Fail-closed month close
# ---------------------------------------------------------------------------


class TestCloseMonthFailClosed:
    def test_close_returns_503_when_transaction_service_unavailable(
        self, client, user1_headers, mock_transaction_port, postgres
    ) -> None:
        from app.domain.exceptions import UpstreamServiceUnavailable

        _create_budget(client, user1_headers)
        mock_transaction_port.get_expenses_by_category.side_effect = UpstreamServiceUnavailable(
            "transaction-service",
        )

        response = client.post(
            "/api/v1/monthly-budgets/close",
            params={"account_id": 1, "month": 6, "year": 2026},
            headers=user1_headers,
        )
        assert response.status_code == 503

        # Måneden er IKKE lukket og der er INGEN outbox-event
        rows = _pg_execute(postgres, "SELECT closed_at FROM monthly_budgets")
        assert rows[0][0] is None
        assert _pg_execute(postgres, "SELECT id FROM outbox_events") == []

    def test_close_succeeds_when_transaction_service_available(
        self, client, user1_headers, mock_transaction_port, postgres
    ) -> None:
        _create_budget(client, user1_headers)
        mock_transaction_port.get_expenses_by_category.return_value = {1: 400.0}

        response = client.post(
            "/api/v1/monthly-budgets/close",
            params={"account_id": 1, "month": 6, "year": 2026},
            headers=user1_headers,
        )
        assert response.status_code == 204

        rows = _pg_execute(postgres, "SELECT closed_at FROM monthly_budgets")
        assert rows[0][0] is not None
        assert len(_pg_execute(postgres, "SELECT id FROM outbox_events")) == 1
