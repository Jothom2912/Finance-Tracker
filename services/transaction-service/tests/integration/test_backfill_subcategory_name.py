"""Integration test for the subcategory_name backfill (Fase 2).

Runs against a real Postgres via testcontainers:
1. A "dirty" auto-categorized row (category_name holds the SUB name) is
   corrected: parent name restored in category_name, sub name moved to
   subcategory_name.
2. A "clean" manual row (category_name already the parent name) is untouched.
3. Re-running the backfill changes nothing (idempotent).

Requires Docker running.
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from app.maintenance.backfill_subcategory_name import BACKFILL_SQL
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# Dirty auto row: category_name wrongly holds the subcategory name.
_DIRTY_ID = 101
# Clean manual row: category_name already holds the parent name.
_CLEAN_ID = 102

_INSERT = """
INSERT INTO transactions
    (id, user_id, account_id, account_name, category_id, category_name,
     subcategory_id, subcategory_name, amount, transaction_type, date,
     categorization_tier)
VALUES
    (:id, 1, 1, 'Checking', :category_id, :category_name,
     :subcategory_id, NULL, 100.00, 'expense', '2026-01-01', :tier)
"""


@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def _migrated_db(postgres):
    url = postgres.get_connection_url()
    os.environ["DATABASE_URL"] = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ["JWT_SECRET"] = "test-secret"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture()
async def session_factory(postgres, _migrated_db):
    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM transactions WHERE id IN (:a, :b)"), {"a": _DIRTY_ID, "b": _CLEAN_ID})
        # category_id=1 is seeded as "Mad & drikke" (parent) by migration 005.
        await conn.execute(
            text(_INSERT),
            {
                "id": _DIRTY_ID,
                "category_id": 1,
                "category_name": "Dagligvarer",  # sub-name in the wrong column
                "subcategory_id": 1,
                "tier": "rule",
            },
        )
        await conn.execute(
            text(_INSERT),
            {
                "id": _CLEAN_ID,
                "category_id": 1,
                "category_name": "Mad & drikke",  # already the parent name
                "subcategory_id": None,
                "tier": "manual",
            },
        )

    yield factory
    await engine.dispose()


async def _row(session_factory, tx_id: int) -> dict:
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT category_name, subcategory_name FROM transactions WHERE id = :id"),
            {"id": tx_id},
        )
        category_name, subcategory_name = result.one()
        return {"category_name": category_name, "subcategory_name": subcategory_name}


async def _run_backfill(session_factory) -> int:
    async with session_factory() as session:
        result = await session.execute(text(BACKFILL_SQL))
        await session.commit()
        return result.rowcount


async def test_dirty_row_is_corrected(session_factory) -> None:
    affected = await _run_backfill(session_factory)
    assert affected == 1  # only the dirty row

    dirty = await _row(session_factory, _DIRTY_ID)
    assert dirty["category_name"] == "Mad & drikke"  # parent restored
    assert dirty["subcategory_name"] == "Dagligvarer"  # sub moved across


async def test_clean_manual_row_is_untouched(session_factory) -> None:
    await _run_backfill(session_factory)

    clean = await _row(session_factory, _CLEAN_ID)
    assert clean["category_name"] == "Mad & drikke"
    assert clean["subcategory_name"] is None


async def test_backfill_is_idempotent(session_factory) -> None:
    first = await _run_backfill(session_factory)
    assert first == 1

    second = await _run_backfill(session_factory)
    assert second == 0  # nothing left to fix

    dirty = await _row(session_factory, _DIRTY_ID)
    assert dirty["category_name"] == "Mad & drikke"
    assert dirty["subcategory_name"] == "Dagligvarer"
