"""Integration tests for transaction soft-delete (P2-25 / P3-37).

Runs against a real Postgres via Testcontainers.  What matters here can
only be observed against the real schema: the partial unique index from
migration 013 is a Postgres object, and the whole point of the change is
that ``deleted_at`` is set on a row that *stays*.

Two properties, both of which the plan calls out as the expensive ones
to get wrong:

* **Invisibility must be total.**  A tombstone gone from ``find_filtered``
  but still counted by ``count_filtered`` is a total the visible rows
  can't add up to.  Both are asserted from the same call site.
* **Deletion must not become an import filter.**  Re-import after a
  delete has to produce a new row — for the fuzzy dedup key *and* for
  the id-bearing path, which goes through the narrowed unique index and
  fails differently (an IntegrityError that reads like a saga failure).

Requires Docker running.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_USER = 4242
_OTHER_USER = 4243


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
async def session(postgres, _migrated_db):  # type: ignore[no-untyped-def]
    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Rows stay uncommitted — visible within the session and rolled back
    # when it closes, so each test gets a clean slate.
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest.fixture()
def repo(session):  # type: ignore[no-untyped-def]
    from app.adapters.outbound.postgres_transaction_repository import PostgresTransactionRepository

    return PostgresTransactionRepository(session)


async def _create(repo, description: str = "Netto", tx_date: date = date(2026, 3, 1), amount: str = "100.00"):  # type: ignore[no-untyped-def]
    from app.domain.entities import TransactionType

    return await repo.create(
        user_id=_USER,
        account_id=1,
        account_name="Checking",
        category_id=None,
        category_name=None,
        amount=Decimal(amount),
        transaction_type=TransactionType.EXPENSE,
        description=description,
        tx_date=tx_date,
    )


# ─────────────────────────────────────────────────────────────
# The row survives; every read path stops seeing it
# ─────────────────────────────────────────────────────────────


async def test_delete_stamps_deleted_at_and_keeps_the_row(repo, session) -> None:  # type: ignore[no-untyped-def]
    """Done-criterion (c): the row is still findable in Postgres."""
    tx = await _create(repo)

    assert await repo.delete(tx.id, _USER) is True

    row = (
        await session.execute(sa.text("SELECT id, deleted_at FROM transactions WHERE id = :id"), {"id": tx.id})
    ).one()
    assert row.deleted_at is not None


async def test_deleted_row_is_gone_from_find_by_id(repo) -> None:  # type: ignore[no-untyped-def]
    tx = await _create(repo)
    await repo.delete(tx.id, _USER)

    assert await repo.find_by_id(tx.id, _USER) is None


async def test_deleted_row_leaves_list_and_total_together(repo) -> None:  # type: ignore[no-untyped-def]
    """The divergence guard: rows and total are read from the same
    ``_filter_clauses``, so a tombstone must disappear from both or the
    header number stops describing the page below it.
    """
    await _create(repo, description="stays")
    doomed = await _create(repo, description="goes")

    before_rows = await repo.find_filtered(_USER)
    before_total = await repo.count_filtered(_USER)
    assert before_total == len(before_rows) == 2

    await repo.delete(doomed.id, _USER)

    after_rows = await repo.find_filtered(_USER)
    after_total = await repo.count_filtered(_USER)

    assert after_total == len(after_rows) == 1
    assert [r.description for r in after_rows] == ["stays"]
    assert before_total - after_total == 1


async def test_update_cannot_resurrect_a_deleted_row(repo) -> None:  # type: ignore[no-untyped-def]
    from app.domain.exceptions import TransactionNotFoundException

    tx = await _create(repo)
    await repo.delete(tx.id, _USER)

    with pytest.raises(TransactionNotFoundException):
        await repo.update(tx.id, _USER, description="edited")


async def test_second_delete_reports_false(repo) -> None:  # type: ignore[no-untyped-def]
    """Scoped on ``deleted_at IS NULL`` — the second call affects no row,
    which the service maps to 404.  Same contract as the hard delete."""
    tx = await _create(repo)

    assert await repo.delete(tx.id, _USER) is True
    assert await repo.delete(tx.id, _USER) is False


async def test_delete_is_scoped_to_the_owner(repo) -> None:  # type: ignore[no-untyped-def]
    """The control for the test above: ``False`` must mean "not yours or
    not there", not "the where-clause matches nothing at all"."""
    tx = await _create(repo)

    assert await repo.delete(tx.id, _OTHER_USER) is False
    assert await repo.find_by_id(tx.id, _USER) is not None


# ─────────────────────────────────────────────────────────────
# Dedup: a tombstone must not block re-import (decision 1)
# ─────────────────────────────────────────────────────────────


async def test_fuzzy_dedup_ignores_deleted_rows(repo) -> None:  # type: ignore[no-untyped-def]
    key = (1, date(2026, 3, 1), Decimal("100.00"), "Netto")
    tx = await _create(repo)

    assert await repo.find_existing_dedup_keys(_USER, [key]) == {key}

    await repo.delete(tx.id, _USER)

    assert await repo.find_existing_dedup_keys(_USER, [key]) == set()


async def test_reimport_after_delete_creates_a_new_row(repo) -> None:  # type: ignore[no-untyped-def]
    tx = await _create(repo)
    await repo.delete(tx.id, _USER)

    reimported = await _create(repo)

    assert reimported.id != tx.id
    assert [r.id for r in await repo.find_filtered(_USER)] == [reimported.id]


async def test_external_id_dedup_ignores_deleted_rows(repo) -> None:  # type: ignore[no-untyped-def]
    """The id-bearing path is the expensive regression: forget
    ``deleted_at IS NULL`` here and re-import doesn't merely double up,
    it raises an IntegrityError against the partial unique index —
    surfacing as a saga failure rather than a dedup bug.
    """
    from app.domain.entities import TransactionType

    (tx,) = await repo.bulk_create(
        [
            {
                "user_id": _USER,
                "account_id": 1,
                "account_name": "Checking",
                "amount": Decimal("77.00"),
                "transaction_type": TransactionType.EXPENSE,
                "description": "Bager",
                "tx_date": date(2026, 3, 3),
                "external_id": "EB-DEL-1",
                "currency": "DKK",
            }
        ]
    )

    assert await repo.find_existing_external_ids(_USER, [(1, "EB-DEL-1")]) == {(1, "EB-DEL-1")}

    await repo.delete(tx.id, _USER)

    assert await repo.find_existing_external_ids(_USER, [(1, "EB-DEL-1")]) == set()

    # …and the re-insert the empty set now invites must actually succeed:
    # the narrowed index from migration 013 has to have freed the slot.
    (reimported,) = await repo.bulk_create(
        [
            {
                "user_id": _USER,
                "account_id": 1,
                "account_name": "Checking",
                "amount": Decimal("77.00"),
                "transaction_type": TransactionType.EXPENSE,
                "description": "Bager",
                "tx_date": date(2026, 3, 3),
                "external_id": "EB-DEL-1",
                "currency": "DKK",
            }
        ]
    )

    assert reimported.id != tx.id
