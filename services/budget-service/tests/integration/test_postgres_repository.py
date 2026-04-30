"""Integration tests for PostgresBudgetRepository.

Tester mod en rigtig PostgreSQL via testcontainers:
1. create   — gemmer et budget og returnerer med id
2. get_by_id — henter et specifikt budget
3. get_all  — filtrerer korrekt på account_id
4. update   — opdaterer amount og category_id
5. delete   — sletter og returnerer True; dobbelt sletning returnerer False

Kræver Docker kørende.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


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
    os.environ["JWT_SECRET"] = "test-secret"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture()
async def session(postgres, _migrated_db):
    sync_url = postgres.get_connection_url()
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")

    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as s:
        yield s

    await engine.dispose()


@pytest.fixture()
def repo(session):
    from app.adapters.outbound.postgres_budget_repository import PostgresBudgetRepository
    return PostgresBudgetRepository(session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateBudget:
    async def test_returns_budget_with_id(self, repo) -> None:
        from app.domain.entities import Budget

        budget = Budget(id=None, amount=1000.0, budget_date=date(2026, 5, 1), account_id=1, category_id=1)
        created = await repo.create(budget)

        assert created.id is not None
        assert created.amount == 1000.0
        assert created.account_id == 1
        assert created.category_id == 1
        assert created.budget_date == date(2026, 5, 1)

    async def test_amount_stored_correctly(self, repo) -> None:
        from app.domain.entities import Budget

        budget = Budget(id=None, amount=2500.50, budget_date=date(2026, 6, 1), account_id=2, category_id=3)
        created = await repo.create(budget)

        assert created.amount == 2500.50


class TestGetBudget:
    async def test_get_by_id_returns_correct_budget(self, repo) -> None:
        from app.domain.entities import Budget

        budget = Budget(id=None, amount=500.0, budget_date=date(2026, 7, 1), account_id=1, category_id=2)
        created = await repo.create(budget)

        fetched = await repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.amount == 500.0

    async def test_get_by_id_returns_none_for_missing(self, repo) -> None:
        result = await repo.get_by_id(99999)
        assert result is None


class TestListBudgets:
    async def test_get_all_filters_by_account_id(self, repo) -> None:
        from app.domain.entities import Budget

        # Opret 2 budgets til account 10, 1 til account 11
        for month in [1, 2]:
            await repo.create(Budget(id=None, amount=100.0, budget_date=date(2026, month, 1), account_id=10, category_id=1))
        await repo.create(Budget(id=None, amount=200.0, budget_date=date(2026, 3, 1), account_id=11, category_id=1))

        result = await repo.get_all(account_id=10)
        assert len(result) >= 2
        assert all(b.account_id == 10 for b in result)

    async def test_get_all_returns_empty_for_unknown_account(self, repo) -> None:
        result = await repo.get_all(account_id=99999)
        assert result == []


class TestUpdateBudget:
    async def test_update_amount(self, repo) -> None:
        from app.domain.entities import Budget

        created = await repo.create(Budget(id=None, amount=300.0, budget_date=date(2026, 8, 1), account_id=5, category_id=1))
        created.amount = 999.0
        updated = await repo.update(created)

        assert updated.amount == 999.0
        assert updated.id == created.id

    async def test_update_category_id(self, repo) -> None:
        from app.domain.entities import Budget

        created = await repo.create(Budget(id=None, amount=400.0, budget_date=date(2026, 9, 1), account_id=6, category_id=1))
        created.category_id = 5
        updated = await repo.update(created)

        assert updated.category_id == 5


class TestDeleteBudget:
    async def test_delete_returns_true(self, repo) -> None:
        from app.domain.entities import Budget

        created = await repo.create(Budget(id=None, amount=100.0, budget_date=date(2026, 10, 1), account_id=7, category_id=1))
        result = await repo.delete(created.id)

        assert result is True

    async def test_deleted_budget_not_found(self, repo) -> None:
        from app.domain.entities import Budget

        created = await repo.create(Budget(id=None, amount=100.0, budget_date=date(2026, 11, 1), account_id=8, category_id=1))
        await repo.delete(created.id)

        fetched = await repo.get_by_id(created.id)
        assert fetched is None

    async def test_delete_nonexistent_returns_false(self, repo) -> None:
        result = await repo.delete(99999)
        assert result is False
