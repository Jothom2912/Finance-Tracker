"""Integration tests for ``PostgresTransactionRepository.find_existing_dedup_keys``.

Runs against a real Postgres via Testcontainers: the batch anti-join
must resolve the whole key list in bulk queries (no per-row SELECT) and
match the bank-sync dedup key ``(user_id, account_id, date, amount,
description)`` exactly — including NULL descriptions, which SQL tuple
``IN`` can't compare and which are therefore matched in Python.

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

_USER = 555
_OTHER_USER = 556

# (account_id, date, amount, description) — seeded for _USER unless noted.
_SEEDED = [
    (1, date(2026, 2, 1), Decimal("100.00"), "Netto"),
    (1, date(2026, 2, 1), Decimal("100.00"), None),  # NULL description
    (2, date(2026, 2, 1), Decimal("100.00"), "Netto"),  # other account
    (1, date(2026, 2, 2), Decimal("59.95"), "Føtex"),
]


@pytest.fixture(scope="module")
def postgres():  # type: ignore[no-untyped-def]
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def _migrated_db(postgres) -> None:  # type: ignore[no-untyped-def]
    url = postgres.get_connection_url()
    os.environ["DATABASE_URL"] = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ["JWT_SECRET"] = "test-secret"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture()
async def repo(postgres, _migrated_db):  # type: ignore[no-untyped-def]
    from app.adapters.outbound.postgres_transaction_repository import PostgresTransactionRepository
    from app.domain.entities import TransactionType

    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        repository = PostgresTransactionRepository(session)
        for account_id, tx_date, amount, description in _SEEDED:
            await repository.create(
                user_id=_USER,
                account_id=account_id,
                account_name="Checking",
                category_id=None,
                category_name=None,
                amount=amount,
                transaction_type=TransactionType.EXPENSE,
                description=description,
                tx_date=tx_date,
            )
        # Identical key under a different user — must never match _USER.
        await repository.create(
            user_id=_OTHER_USER,
            account_id=1,
            account_name="Checking",
            category_id=None,
            category_name=None,
            amount=Decimal("100.00"),
            transaction_type=TransactionType.EXPENSE,
            description="Netto",
            tx_date=date(2026, 2, 1),
        )
        # Rows stay uncommitted — visible to the repo within this session
        # and rolled back automatically when it closes, so each test gets
        # a clean slate.
        yield repository

    await engine.dispose()


async def test_existing_key_is_found(repo) -> None:  # type: ignore[no-untyped-def]
    existing = await repo.find_existing_dedup_keys(
        _USER,
        [(1, date(2026, 2, 1), Decimal("100.00"), "Netto")],
    )
    assert existing == {(1, date(2026, 2, 1), Decimal("100.00"), "Netto")}


async def test_null_description_matches_none_key(repo) -> None:  # type: ignore[no-untyped-def]
    """tuple_(...).in_() can't match NULLs — the Python-side description
    comparison must, or every no-description row imports twice."""
    existing = await repo.find_existing_dedup_keys(
        _USER,
        [(1, date(2026, 2, 1), Decimal("100.00"), None)],
    )
    assert existing == {(1, date(2026, 2, 1), Decimal("100.00"), None)}


async def test_description_mismatch_is_not_a_duplicate(repo) -> None:  # type: ignore[no-untyped-def]
    """Same (account, date, amount) triple but a different description is
    a distinct transaction — the candidate superset must be filtered."""
    existing = await repo.find_existing_dedup_keys(
        _USER,
        [(1, date(2026, 2, 1), Decimal("100.00"), "Kaffebar")],
    )
    assert existing == set()


async def test_other_users_rows_never_match(repo) -> None:  # type: ignore[no-untyped-def]
    existing = await repo.find_existing_dedup_keys(
        999,
        [(1, date(2026, 2, 1), Decimal("100.00"), "Netto")],
    )
    assert existing == set()


async def test_amount_matches_across_decimal_scales(repo) -> None:  # type: ignore[no-untyped-def]
    """Decimal('100.0') and the stored NUMERIC(12,2) 100.00 are the same
    amount — scale differences in parsed input must not defeat dedup."""
    existing = await repo.find_existing_dedup_keys(
        _USER,
        [(1, date(2026, 2, 1), Decimal("100.0"), "Netto")],
    )
    assert len(existing) == 1


async def test_batch_returns_only_existing_subset(repo) -> None:  # type: ignore[no-untyped-def]
    new_key = (1, date(2026, 3, 15), Decimal("42.00"), "Ny butik")
    existing = await repo.find_existing_dedup_keys(
        _USER,
        [
            (1, date(2026, 2, 1), Decimal("100.00"), "Netto"),
            (2, date(2026, 2, 1), Decimal("100.00"), "Netto"),
            (1, date(2026, 2, 2), Decimal("59.95"), "Føtex"),
            new_key,
        ],
    )
    assert existing == {
        (1, date(2026, 2, 1), Decimal("100.00"), "Netto"),
        (2, date(2026, 2, 1), Decimal("100.00"), "Netto"),
        (1, date(2026, 2, 2), Decimal("59.95"), "Føtex"),
    }


async def test_empty_key_list_returns_empty_set(repo) -> None:  # type: ignore[no-untyped-def]
    assert await repo.find_existing_dedup_keys(_USER, []) == set()
