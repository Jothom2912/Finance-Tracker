"""Integration tests for TransactionCreatedConsumer idempotency.

Tests that the consumer handles duplicate messages correctly:
1. Sequential redelivery: same message_id processed twice → second is no-op
2. Concurrent race: two consumers process same message → one wins, one rolls back

Requires Docker (testcontainers spins up a Postgres).
"""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer


def _make_rule_engine():
    """Minimal rule engine: 'netto' -> subcategory 1, category 1."""
    from app.adapters.outbound.rule_engine import RuleEngine

    return (
        RuleEngine(
            keyword_mappings=[("netto", "Dagligvarer")],
            subcategory_lookup={"Dagligvarer": (1, 1), "Anden": (32, 8)},
        ),
        32,
        8,
    )


def _make_message(payload: dict, message_id: str) -> AsyncMock:
    """Create a mock AbstractIncomingMessage."""
    msg = AsyncMock()
    msg.body = json.dumps(payload).encode("utf-8")
    msg.headers = {}
    payload_with_id = {**payload, "correlation_id": message_id}
    msg.body = json.dumps(payload_with_id).encode("utf-8")
    return msg


@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def sync_engine(postgres):
    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ["DATABASE_URL"] = async_url
    os.environ["JWT_SECRET"] = "test-secret"

    eng = create_engine(url)
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")
    return eng


@pytest.fixture()
async def session_factory(postgres, sync_engine):
    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM processed_events"))
        await conn.execute(text("DELETE FROM outbox_events"))
        await conn.execute(text("DELETE FROM categorization_results"))

    yield factory

    await engine.dispose()


@pytest.fixture()
async def consumer(session_factory):
    """Consumer with patched session_factory to use test DB."""
    import app.workers.transaction_consumer as tc_module

    original_factory = tc_module.async_session_factory
    tc_module.async_session_factory = session_factory

    engine, fallback_sub, fallback_cat = _make_rule_engine()
    c = tc_module.TransactionCreatedConsumer(engine, fallback_sub, fallback_cat)

    yield c

    tc_module.async_session_factory = original_factory


class TestSequentialIdempotency:
    """Same message delivered twice sequentially."""

    async def test_second_delivery_is_noop(self, consumer, session_factory) -> None:
        from app.models import CategorizationResultModel, OutboxEventModel, ProcessedEventModel

        message_id = str(uuid4())
        payload = {
            "correlation_id": message_id,
            "event_type": "transaction.created",
            "transaction_id": 42,
            "description": "Netto Nordhavn",
            "amount": "-150.00",
        }
        msg1 = _make_message(payload, message_id)
        msg2 = _make_message(payload, message_id)

        await consumer._on_message(msg1)

        async with session_factory() as session:
            results = (await session.execute(select(CategorizationResultModel))).scalars().all()
            outbox = (await session.execute(select(OutboxEventModel))).scalars().all()
            inbox = (await session.execute(select(ProcessedEventModel))).scalars().all()
            assert len(results) == 1
            assert len(outbox) == 1
            assert len(inbox) == 1

        await consumer._on_message(msg2)

        async with session_factory() as session:
            results = (await session.execute(select(CategorizationResultModel))).scalars().all()
            outbox = (await session.execute(select(OutboxEventModel))).scalars().all()
            inbox = (await session.execute(select(ProcessedEventModel))).scalars().all()
            assert len(results) == 1, f"Expected 1 result, got {len(results)}"
            assert len(outbox) == 1, f"Expected 1 outbox event, got {len(outbox)}"
            assert len(inbox) == 1, f"Expected 1 inbox row, got {len(inbox)}"

        msg1.ack.assert_awaited()
        msg2.ack.assert_awaited()

    async def test_different_messages_both_processed(self, consumer, session_factory) -> None:
        from app.models import CategorizationResultModel

        msg_a = _make_message(
            {"transaction_id": 100, "description": "Netto", "amount": "-50.00", "event_type": "transaction.created"},
            str(uuid4()),
        )
        msg_b = _make_message(
            {"transaction_id": 200, "description": "Lidl", "amount": "-30.00", "event_type": "transaction.created"},
            str(uuid4()),
        )

        await consumer._on_message(msg_a)
        await consumer._on_message(msg_b)

        async with session_factory() as session:
            results = (await session.execute(select(CategorizationResultModel))).scalars().all()
            assert len(results) == 2


class TestConcurrentRaceCondition:
    """Two consumers process the same message simultaneously."""

    async def test_concurrent_same_message_only_one_result(self, consumer, session_factory) -> None:
        from app.models import CategorizationResultModel, OutboxEventModel, ProcessedEventModel

        message_id = str(uuid4())
        payload = {
            "correlation_id": message_id,
            "event_type": "transaction.created",
            "transaction_id": 99,
            "description": "Netto City",
            "amount": "-100.00",
        }
        msg1 = _make_message(payload, message_id)
        msg2 = _make_message(payload, message_id)

        results = await asyncio.gather(
            consumer._on_message(msg1),
            consumer._on_message(msg2),
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, Exception):
                pytest.fail(f"Consumer raised unhandled exception: {r}")

        async with session_factory() as session:
            result_rows = (await session.execute(select(CategorizationResultModel))).scalars().all()
            outbox_rows = (await session.execute(select(OutboxEventModel))).scalars().all()
            inbox_rows = (await session.execute(select(ProcessedEventModel))).scalars().all()

            assert len(result_rows) == 1, f"Expected 1 result, got {len(result_rows)}"
            assert len(outbox_rows) == 1, f"Expected 1 outbox, got {len(outbox_rows)}"
            assert len(inbox_rows) == 1, f"Expected 1 inbox, got {len(inbox_rows)}"

        msg1.ack.assert_awaited()
        msg2.ack.assert_awaited()
