"""Integration tests for budget-service REST API.

Tester HTTP-laget end-to-end mod en rigtig PostgreSQL via testcontainers.
Bruger FastAPI's TestClient med dependency overrides til:
- Database session (testcontainers PostgreSQL)
- CategoryPort (mock — fail-open og kategori-ikke-fundet)

Kræver Docker kørende.
"""

from __future__ import annotations

import os
from datetime import date
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
    """Returnerer den async DATABASE_URL som string (module-scoped)."""
    sync_url = postgres.get_connection_url()
    return sync_url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")


@pytest.fixture(autouse=True)
def clean_db(postgres, _migrated_db):
    """Tøm budgets-tabellen før hver test via synkron psycopg2 (undgår event-loop konflikter)."""
    import psycopg2
    # get_connection_url() kan returnere postgresql+psycopg2://... — strip dialekt-prefix
    raw_url = postgres.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    conn = psycopg2.connect(raw_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM budgets")
    cur.close()
    conn.close()


@pytest.fixture()
def client(async_db_url):
    """TestClient med dependency overrides.

    Opretter en ny async engine INDE i TestClient's event loop for at undgå
    'Future attached to a different loop' fejl.
    """
    from app.adapters.outbound.postgres_budget_repository import PostgresBudgetRepository
    from app.application.ports.outbound import ICategoryPort
    from app.application.service import BudgetService
    from app.dependencies import get_budget_service
    from app.main import app

    mock_category_port = AsyncMock(spec=ICategoryPort)
    mock_category_port.exists.return_value = True

    _url = async_db_url

    async def override_get_budget_service():
        """Opretter engine og session i TestClient's event loop."""
        engine = create_async_engine(_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = PostgresBudgetRepository(session)
            yield BudgetService(repo=repo, category_port=mock_category_port)
        await engine.dispose()

    app.dependency_overrides[get_budget_service] = override_get_budget_service

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers():
    return {"Authorization": f"Bearer {_make_token(user_id=1)}"}


# ---------------------------------------------------------------------------
# Tests: Autentificering
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_get_budgets_without_token_returns_401(self, client) -> None:
        response = client.get("/api/v1/budgets/", params={"account_id": 1})
        assert response.status_code == 401

    def test_get_budgets_with_invalid_token_returns_401(self, client) -> None:
        response = client.get(
            "/api/v1/budgets/",
            params={"account_id": 1},
            headers={"Authorization": "Bearer ugyldig.token.her"},
        )
        assert response.status_code == 401

    def test_get_budgets_with_valid_token_returns_200(self, client, auth_headers) -> None:
        response = client.get("/api/v1/budgets/", params={"account_id": 1}, headers=auth_headers)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Liste budgets
# ---------------------------------------------------------------------------

class TestListBudgets:
    def test_empty_list_for_new_account(self, client, auth_headers) -> None:
        response = client.get("/api/v1/budgets/", params={"account_id": 42}, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_budgets_for_given_account(self, client, auth_headers) -> None:
        # Opret 2 budgets til account 1, 1 til account 2
        client.post("/api/v1/budgets/", json={"amount": 100, "month": 1, "year": 2026, "account_id": 1, "category_id": 1}, headers=auth_headers)
        client.post("/api/v1/budgets/", json={"amount": 200, "month": 2, "year": 2026, "account_id": 1, "category_id": 1}, headers=auth_headers)
        client.post("/api/v1/budgets/", json={"amount": 300, "month": 3, "year": 2026, "account_id": 2, "category_id": 1}, headers=auth_headers)

        response = client.get("/api/v1/budgets/", params={"account_id": 1}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(b["account_id"] == 1 for b in data)


# ---------------------------------------------------------------------------
# Tests: Opret budget
# ---------------------------------------------------------------------------

class TestCreateBudget:
    def test_create_returns_201_with_id(self, client, auth_headers) -> None:
        response = client.post(
            "/api/v1/budgets/",
            json={"amount": 1500.0, "month": 5, "year": 2026, "account_id": 1, "category_id": 1},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["amount"] == 1500.0
        assert data["account_id"] == 1
        assert data["category_id"] == 1

    def test_create_converts_month_year_to_budget_date(self, client, auth_headers) -> None:
        response = client.post(
            "/api/v1/budgets/",
            json={"amount": 500.0, "month": 3, "year": 2026, "account_id": 1, "category_id": 1},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["budget_date"] == "2026-03-01"

    def test_create_with_budget_date_directly(self, client, auth_headers) -> None:
        response = client.post(
            "/api/v1/budgets/",
            json={"amount": 750.0, "budget_date": "2026-07-01", "account_id": 1, "category_id": 2},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["budget_date"] == "2026-07-01"

    def test_create_with_negative_amount_returns_422(self, client, auth_headers) -> None:
        response = client.post(
            "/api/v1/budgets/",
            json={"amount": -100.0, "month": 5, "year": 2026, "account_id": 1, "category_id": 1},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_without_account_id_returns_422(self, client, auth_headers) -> None:
        response = client.post(
            "/api/v1/budgets/",
            json={"amount": 500.0, "month": 5, "year": 2026, "category_id": 1},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Hent specifikt budget
# ---------------------------------------------------------------------------

class TestGetBudget:
    def test_get_existing_budget_returns_200(self, client, auth_headers) -> None:
        created = client.post(
            "/api/v1/budgets/",
            json={"amount": 800.0, "month": 6, "year": 2026, "account_id": 3, "category_id": 1},
            headers=auth_headers,
        ).json()

        response = client.get(f"/api/v1/budgets/{created['id']}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_nonexistent_budget_returns_404(self, client, auth_headers) -> None:
        response = client.get("/api/v1/budgets/99999", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Opdater budget
# ---------------------------------------------------------------------------

class TestUpdateBudget:
    def test_update_amount_returns_200(self, client, auth_headers) -> None:
        created = client.post(
            "/api/v1/budgets/",
            json={"amount": 1000.0, "month": 8, "year": 2026, "account_id": 4, "category_id": 1},
            headers=auth_headers,
        ).json()

        response = client.put(
            f"/api/v1/budgets/{created['id']}",
            json={"amount": 2000.0},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["amount"] == 2000.0

    def test_update_nonexistent_budget_returns_404(self, client, auth_headers) -> None:
        response = client.put(
            "/api/v1/budgets/99999",
            json={"amount": 500.0},
            headers=auth_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Slet budget
# ---------------------------------------------------------------------------

class TestDeleteBudget:
    def test_delete_existing_budget_returns_204(self, client, auth_headers) -> None:
        created = client.post(
            "/api/v1/budgets/",
            json={"amount": 300.0, "month": 9, "year": 2026, "account_id": 5, "category_id": 1},
            headers=auth_headers,
        ).json()

        response = client.delete(f"/api/v1/budgets/{created['id']}", headers=auth_headers)
        assert response.status_code == 204

    def test_deleted_budget_is_gone(self, client, auth_headers) -> None:
        created = client.post(
            "/api/v1/budgets/",
            json={"amount": 300.0, "month": 10, "year": 2026, "account_id": 5, "category_id": 1},
            headers=auth_headers,
        ).json()

        client.delete(f"/api/v1/budgets/{created['id']}", headers=auth_headers)
        response = client.get(f"/api/v1/budgets/{created['id']}", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_nonexistent_budget_returns_404(self, client, auth_headers) -> None:
        response = client.delete("/api/v1/budgets/99999", headers=auth_headers)
        assert response.status_code == 404
