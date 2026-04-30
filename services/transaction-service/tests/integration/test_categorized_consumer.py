"""Integration tests for TransactionCategorizedConsumer.

Tests against a real Postgres via testcontainers:
1. Consumer updates transaction with cat-service's categorization
2. Idempotency: same message_id twice = one update
3. No-op when categorization is unchanged

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
from sqlalchemy import select, text
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

    yield factory
    await engine.dispose()


@pytest.fixture()
async def _seed_transaction(session_factory):
    """Insert a test transaction (id=1) with monolith categorization."""
    async with session_factory() as session:
        await session.execute(text("DELETE FROM transactions WHERE id IN (1, 2)"))
        await session.execute(
            text(
                "INSERT INTO transactions (id, user_id, account_id, account_name, "
                "amount, transaction_type, description, date, "
                "subcategory_id, categorization_tier, categorization_confidence) "
                "VALUES (1, 1, 1, 'Test', 150.00, 'expense', 'Netto Nordhavn', '2026-04-20', "
                "1, 'rule', 'high')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO transactions (id, user_id, account_id, account_name, "
                "amount, transaction_type, description, date) "
                "VALUES (2, 1, 1, 'Test', 50.00, 'expense', 'Unknown shop', '2026-04-20')"
            )
        )
        await session.execute(
            text("SELECT setval('transactions_id_seq', (SELECT COALESCE(MAX(id), 0) FROM transactions))")
        )
        await session.commit()


@pytest.fixture()
async def consumer(session_factory, _seed_transaction):
    import app.workers.categorized_consumer as consumer_module

    original = consumer_module.async_session_factory
    consumer_module.async_session_factory = session_factory
    c = consumer_module.TransactionCategorizedConsumer()
    yield c
    consumer_module.async_session_factory = original


class TestConsumerUpdatesTransaction:
    async def test_overwrites_with_cat_service_result(self, consumer, session_factory) -> None:
        from app.models import TransactionModel

        msg = _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": 1,
                "subcategory_id": 7,
                "tier": "rule",
                "confidence": "high",
                "model_version": "rules-keyword-v1",
            },
            str(uuid4()),
        )

        await consumer._on_message(msg)

        async with session_factory() as session:
            tx = (await session.execute(select(TransactionModel).where(TransactionModel.id == 1))).scalar_one()
            assert tx.subcategory_id == 7
            assert tx.categorization_tier == "rule"
            assert tx.categorization_confidence == "high"

        msg.ack.assert_awaited()

    async def test_fills_uncategorized_transaction(self, consumer, session_factory) -> None:
        from app.models import TransactionModel

        msg = _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": 2,
                "subcategory_id": 32,
                "tier": "fallback",
                "confidence": "low",
                "model_version": "rules-keyword-v1",
            },
            str(uuid4()),
        )

        await consumer._on_message(msg)

        async with session_factory() as session:
            tx = (await session.execute(select(TransactionModel).where(TransactionModel.id == 2))).scalar_one()
            assert tx.subcategory_id == 32
            assert tx.categorization_tier == "fallback"

        msg.ack.assert_awaited()


class TestConsumerIdempotency:
    async def test_same_message_twice_updates_once(self, consumer, session_factory) -> None:
        from app.models import ProcessedEventModel

        message_id = str(uuid4())
        msg1 = _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": 1,
                "subcategory_id": 11,
                "tier": "rule",
                "confidence": "high",
                "model_version": "rules-keyword-v1",
            },
            message_id,
        )
        msg2 = _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": 1,
                "subcategory_id": 11,
                "tier": "rule",
                "confidence": "high",
                "model_version": "rules-keyword-v1",
            },
            message_id,
        )

        await consumer._on_message(msg1)
        await consumer._on_message(msg2)

        async with session_factory() as session:
            inbox = (await session.execute(select(ProcessedEventModel))).scalars().all()
            assert len(inbox) == 1

        msg1.ack.assert_awaited()
        msg2.ack.assert_awaited()


class TestConsumerNoopOnSameData:
    async def test_no_update_when_data_unchanged(self, consumer, session_factory) -> None:
        from app.models import TransactionModel

        msg = _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": 1,
                "subcategory_id": 1,
                "tier": "rule",
                "confidence": "high",
                "model_version": "rules-keyword-v1",
            },
            str(uuid4()),
        )

        await consumer._on_message(msg)

        async with session_factory() as session:
            tx = (await session.execute(select(TransactionModel).where(TransactionModel.id == 1))).scalar_one()
            assert tx.subcategory_id == 1
            assert tx.categorization_tier == "rule"

        msg.ack.assert_awaited()
