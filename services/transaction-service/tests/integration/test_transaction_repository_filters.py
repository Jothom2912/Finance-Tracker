"""Integration tests for ``PostgresTransactionRepository.find_filtered``.

Runs against a real Postgres via testcontainers: every provided filter
(account, category, date range, transaction type) must combine in ONE
SQL query, with deterministic date-desc/id-desc ordering and real
OFFSET/LIMIT pagination.

Requires Docker running.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_USER = 777
_OTHER_USER = 888

# (account_id, type, date, description, user_id, category_id) — creation
# order matters: ids are ascending, so same-date rows test the id tie-break.
_ROWS = [
    (1, "expense", date(2026, 1, 15), "before range", _USER, None),
    (1, "expense", date(2026, 2, 1), "in range #1", _USER, 1),
    (1, "expense", date(2026, 2, 10), "in range #2", _USER, None),
    (1, "income", date(2026, 2, 10), "income same date", _USER, None),
    (1, "expense", date(2026, 2, 20), "in range #3", _USER, None),
    (1, "expense", date(2026, 3, 5), "after range", _USER, None),
    (2, "expense", date(2026, 2, 15), "other account", _USER, None),
    (1, "expense", date(2026, 2, 12), "other user", _OTHER_USER, None),
]


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
async def repo(postgres, _migrated_db):
    from app.adapters.outbound.postgres_transaction_repository import PostgresTransactionRepository
    from app.domain.entities import TransactionType

    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        repository = PostgresTransactionRepository(session)
        for account_id, tx_type, tx_date, description, user_id, category_id in _ROWS:
            await repository.create(
                user_id=user_id,
                account_id=account_id,
                account_name="Checking",
                # category_id=1 is seeded as "Mad & drikke" by migration 005.
                category_id=category_id,
                category_name="Mad & drikke" if category_id is not None else None,
                amount=Decimal("100.00"),
                transaction_type=TransactionType(tx_type),
                description=description,
                tx_date=tx_date,
            )
        # Rows stay uncommitted — visible to the repo within this session
        # and rolled back automatically when it closes, so each test gets
        # a clean slate.
        yield repository

    await engine.dispose()


async def test_all_filters_combine_in_one_query(repo) -> None:
    from app.domain.entities import TransactionType

    results = await repo.find_filtered(
        _USER,
        account_id=1,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        transaction_type=TransactionType.EXPENSE,
    )

    # Excludes: dates outside the range, the income row, the other
    # account and the other user.  Ordered date desc.
    assert [t.description for t in results] == ["in range #3", "in range #2", "in range #1"]


async def test_pagination_applies_on_top_of_filters(repo) -> None:
    from app.domain.entities import TransactionType

    page = await repo.find_filtered(
        _USER,
        account_id=1,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        transaction_type=TransactionType.EXPENSE,
        skip=1,
        limit=2,
    )

    assert [t.description for t in page] == ["in range #2", "in range #1"]


async def test_category_filter_combines_with_date_range(repo) -> None:
    results = await repo.find_filtered(
        _USER,
        category_id=1,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert [t.description for t in results] == ["in range #1"]


async def test_same_date_rows_order_by_id_desc(repo) -> None:
    results = await repo.find_filtered(
        _USER,
        account_id=1,
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    # Same date — the later-created (higher id) row comes first.
    assert [t.description for t in results] == ["income same date", "in range #2"]


async def test_limit_applies_without_other_filters(repo) -> None:
    results = await repo.find_filtered(_USER, limit=3)

    assert [t.description for t in results] == ["after range", "in range #3", "other account"]
