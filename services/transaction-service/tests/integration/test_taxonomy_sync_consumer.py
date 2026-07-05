"""Integration tests for TaxonomySyncConsumer.

Tests against a real Postgres via testcontainers:
1. Upsert semantics for category.* and subcategory.* (created/updated)
2. Self-healing: updated-for-missing-row creates it
3. deleted removes the local row; deleted-when-missing is a no-op
4. Idempotency: same message_id twice = one effect, second delivery acked

Requires Docker running.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


def _make_message(payload: dict, message_id: str) -> AsyncMock:
    msg = AsyncMock()
    full_payload = {**payload, "correlation_id": message_id}
    msg.body = json.dumps(full_payload).encode("utf-8")
    msg.headers = {}
    return msg


@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def _migrated_db(postgres):
    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ["DATABASE_URL"] = async_url
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
        await conn.execute(text("DELETE FROM processed_events"))
        await conn.execute(text("DELETE FROM categories WHERE id >= 100"))
        await conn.execute(text("DELETE FROM subcategories WHERE id >= 100"))

    yield factory
    await engine.dispose()


@pytest.fixture()
async def consumer(session_factory):
    import app.workers.taxonomy_sync_consumer as consumer_module

    original = consumer_module.async_session_factory
    consumer_module.async_session_factory = session_factory
    c = consumer_module.TaxonomySyncConsumer()
    yield c
    consumer_module.async_session_factory = original


async def _fetch_one(session_factory, sql: str, **params):
    async with session_factory() as session:
        result = await session.execute(text(sql), params)
        return result.fetchone()


class TestCategorySync:
    async def test_created_inserts_row(self, consumer, session_factory) -> None:
        msg = _make_message(
            {
                "event_type": "category.created",
                "category_id": 100,
                "name": "Ferie",
                "category_type": "expense",
                "display_order": 11,
            },
            str(uuid4()),
        )
        await consumer._on_message(msg)
        msg.ack.assert_awaited_once()

        row = await _fetch_one(session_factory, "SELECT name, type FROM categories WHERE id = 100")
        assert row == ("Ferie", "expense")

    async def test_updated_for_missing_row_creates_it(self, consumer, session_factory) -> None:
        """Self-healing: full-state events let an update act as create."""
        msg = _make_message(
            {
                "event_type": "category.updated",
                "category_id": 101,
                "name": "Gaver",
                "category_type": "expense",
            },
            str(uuid4()),
        )
        await consumer._on_message(msg)

        row = await _fetch_one(session_factory, "SELECT name FROM categories WHERE id = 101")
        assert row == ("Gaver",)

    async def test_updated_overwrites_existing(self, consumer, session_factory) -> None:
        await consumer._on_message(
            _make_message(
                {"event_type": "category.created", "category_id": 102, "name": "Old", "category_type": "expense"},
                str(uuid4()),
            )
        )
        await consumer._on_message(
            _make_message(
                {"event_type": "category.updated", "category_id": 102, "name": "New", "category_type": "income"},
                str(uuid4()),
            )
        )
        row = await _fetch_one(session_factory, "SELECT name, type FROM categories WHERE id = 102")
        assert row == ("New", "income")

    async def test_deleted_removes_row_and_missing_is_noop(self, consumer, session_factory) -> None:
        await consumer._on_message(
            _make_message(
                {"event_type": "category.created", "category_id": 103, "name": "Temp", "category_type": "expense"},
                str(uuid4()),
            )
        )
        await consumer._on_message(
            _make_message(
                {"event_type": "category.deleted", "category_id": 103, "name": "Temp", "category_type": "expense"},
                str(uuid4()),
            )
        )
        row = await _fetch_one(session_factory, "SELECT 1 FROM categories WHERE id = 103")
        assert row is None

        # Deleting again (missing row) must ack without error.
        msg = _make_message(
            {"event_type": "category.deleted", "category_id": 103, "name": "Temp", "category_type": "expense"},
            str(uuid4()),
        )
        await consumer._on_message(msg)
        msg.ack.assert_awaited_once()
        msg.nack.assert_not_awaited()


class TestSubcategorySync:
    async def test_created_inserts_row(self, consumer, session_factory) -> None:
        msg = _make_message(
            {
                "event_type": "subcategory.created",
                "subcategory_id": 100,
                "name": "Kaffe",
                "category_id": 1,
                "is_default": False,
            },
            str(uuid4()),
        )
        await consumer._on_message(msg)

        row = await _fetch_one(
            session_factory,
            "SELECT name, category_id, is_default FROM subcategories WHERE id = 100",
        )
        assert row == ("Kaffe", 1, False)

    async def test_updated_reparents_and_renames(self, consumer, session_factory) -> None:
        await consumer._on_message(
            _make_message(
                {"event_type": "subcategory.created", "subcategory_id": 101, "name": "A", "category_id": 1},
                str(uuid4()),
            )
        )
        await consumer._on_message(
            _make_message(
                {"event_type": "subcategory.updated", "subcategory_id": 101, "name": "B", "category_id": 2},
                str(uuid4()),
            )
        )
        row = await _fetch_one(
            session_factory, "SELECT name, category_id FROM subcategories WHERE id = 101"
        )
        assert row == ("B", 2)

    async def test_updated_for_missing_row_creates_it(self, consumer, session_factory) -> None:
        await consumer._on_message(
            _make_message(
                {"event_type": "subcategory.updated", "subcategory_id": 102, "name": "Selfheal", "category_id": 3},
                str(uuid4()),
            )
        )
        row = await _fetch_one(session_factory, "SELECT name FROM subcategories WHERE id = 102")
        assert row == ("Selfheal",)

    async def test_deleted_removes_row(self, consumer, session_factory) -> None:
        await consumer._on_message(
            _make_message(
                {"event_type": "subcategory.created", "subcategory_id": 103, "name": "Temp", "category_id": 1},
                str(uuid4()),
            )
        )
        await consumer._on_message(
            _make_message(
                {"event_type": "subcategory.deleted", "subcategory_id": 103, "name": "Temp", "category_id": 1},
                str(uuid4()),
            )
        )
        row = await _fetch_one(session_factory, "SELECT 1 FROM subcategories WHERE id = 103")
        assert row is None


class TestIdempotency:
    async def test_duplicate_message_id_processed_once(self, consumer, session_factory) -> None:
        message_id = str(uuid4())
        payload = {
            "event_type": "category.created",
            "category_id": 110,
            "name": "Dublet",
            "category_type": "expense",
        }

        first = _make_message(payload, message_id)
        await consumer._on_message(first)

        # Mutate the payload — a duplicate delivery must NOT apply it.
        second = _make_message({**payload, "name": "Andet navn"}, message_id)
        await consumer._on_message(second)
        second.ack.assert_awaited_once()

        row = await _fetch_one(session_factory, "SELECT name FROM categories WHERE id = 110")
        assert row == ("Dublet",)

        inbox = await _fetch_one(
            session_factory,
            "SELECT COUNT(*) FROM processed_events WHERE message_id = :mid",
            mid=message_id,
        )
        assert inbox == (1,)

    async def test_unknown_event_type_acks_without_inbox_row(self, consumer, session_factory) -> None:
        message_id = str(uuid4())
        msg = _make_message({"event_type": "category.exploded", "category_id": 1}, message_id)
        await consumer._on_message(msg)
        msg.ack.assert_awaited_once()

        inbox = await _fetch_one(
            session_factory,
            "SELECT COUNT(*) FROM processed_events WHERE message_id = :mid",
            mid=message_id,
        )
        assert inbox == (0,)
