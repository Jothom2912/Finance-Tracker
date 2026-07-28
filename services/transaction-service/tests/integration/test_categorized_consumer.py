"""Integration tests for TransactionCategorizedConsumer.

Tests against a real Postgres via testcontainers:
1. Consumer updates transaction with cat-service's categorization
2. Idempotency: same message_id twice = one update
3. No-op when categorization is unchanged

Requires Docker running.
"""

from __future__ import annotations

import json
import logging
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

    async def test_v2_event_category_name_applied_without_local_lookup(self, consumer, session_factory) -> None:
        """v2 events carry the parent name — it must be applied even when
        the category_id is unknown in the local read copy (the old
        stale-name window)."""
        from app.models import TransactionModel

        msg = _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": 1,
                "category_id": 9999,  # not in the local categories read copy
                "category_name": "Ferie",
                "subcategory_id": 7,
                "subcategory_name": "Hotel",
                "tier": "rule",
                "confidence": "high",
                "model_version": "rules-keyword-v1",
            },
            str(uuid4()),
        )

        await consumer._on_message(msg)

        async with session_factory() as session:
            tx = (await session.execute(select(TransactionModel).where(TransactionModel.id == 1))).scalar_one()
            assert tx.category_id == 9999
            assert tx.category_name == "Ferie"
            assert tx.subcategory_name == "Hotel"

        msg.ack.assert_awaited()

    async def test_v1_event_without_category_name_resolves_locally(self, consumer, session_factory) -> None:
        """Old payloads (empty category_name) fall back to the local
        categories read copy for the parent name."""
        from app.models import TransactionModel

        msg = _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": 1,
                "category_id": 1,  # seeded: "Mad & drikke"
                "subcategory_id": 1,
                "subcategory_name": "Dagligvarer",
                "tier": "rule",
                "confidence": "high",
                "model_version": "rules-keyword-v1",
            },
            str(uuid4()),
        )

        await consumer._on_message(msg)

        async with session_factory() as session:
            tx = (await session.execute(select(TransactionModel).where(TransactionModel.id == 1))).scalar_one()
            assert tx.category_id == 1
            assert tx.category_name == "Mad & drikke"
            assert tx.subcategory_name == "Dagligvarer"

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


class TestGoneVsNotYet:
    """P2-25: the two states that used to look identical.

    Before soft-delete, a categorization for a deleted transaction and one
    that raced ahead of its INSERT were the same observation — "row not
    found" — so the consumer retried both.  For the deleted one that meant
    five retries with 1/2/4/8/16 s backoff on a prefetch=1 consumer, then
    the DLQ.  See
    ``dev-notes/findings/2026-07-25-transaction-hard-delete-categorized-dlq.md``.

    **Which change fixes which half — measured, by deleting the branch and
    re-running this class.**  The soft-delete alone (migration 013 + the
    repository) already kills the DLQ path: the row now exists, so
    ``_get_transaction`` returns it and nothing backs off.  Only
    ``test_deleted_transaction_is_not_categorized`` fails without the
    branch, and that is the branch's real job — a tombstone must not get
    its categorization fields rewritten, and the skip must be traceable in
    the log.  The backoff assertions below are regression guards on the
    property soft-delete bought, not evidence for the branch; saying
    otherwise would make this docstring the untrue kind.
    """

    @staticmethod
    def _msg(transaction_id: int) -> AsyncMock:
        return _make_message(
            {
                "event_type": "transaction.categorized",
                "transaction_id": transaction_id,
                "subcategory_id": 7,
                "tier": "rule",
                "confidence": "high",
            },
            str(uuid4()),
        )

    async def test_deleted_transaction_is_acked_without_backoff(self, consumer, session_factory, monkeypatch) -> None:
        """Done-criterion (b): acked, no DLQ, no 16 s sleep on a
        prefetch=1 consumer.

        This holds from migration 013 onward regardless of the branch —
        see the class docstring.  It is kept because it is the criterion
        the finding was written against, and because it would catch a
        future change that reintroduced hard-delete underneath.
        """
        slept: list[int] = []
        monkeypatch.setattr(
            consumer,
            "_stale_backoff",
            AsyncMock(side_effect=lambda *a, **k: slept.append(1)),
        )

        async with session_factory() as session:
            await session.execute(text("UPDATE transactions SET deleted_at = now() WHERE id = 1"))
            await session.commit()

        msg = self._msg(1)
        await consumer._on_message(msg)

        msg.ack.assert_awaited()
        msg.nack.assert_not_awaited()
        assert slept == []

    async def test_deleted_transaction_is_not_categorized(self, consumer, session_factory, caplog) -> None:
        """The load-bearing one: acking must mean "we skipped it", not "we
        applied it and said nothing".

        Without the ``deleted_at is not None`` branch this is the single
        assertion in the class that fails — the consumer happily rewrites
        a tombstone's categorization fields.
        """
        from app.models import TransactionModel

        async with session_factory() as session:
            await session.execute(text("UPDATE transactions SET deleted_at = now() WHERE id = 1"))
            await session.commit()

        with caplog.at_level(logging.INFO, logger="app.workers.categorized_consumer"):
            await consumer._on_message(self._msg(1))

        async with session_factory() as session:
            tx = (await session.execute(select(TransactionModel).where(TransactionModel.id == 1))).scalar_one()
            # Seeded values from ``_seed_transaction`` — untouched.
            assert tx.subcategory_id == 1

        # The skip must leave a trace naming the transaction: it is the only
        # signal if deleted_at were ever set too broadly and this branch
        # started swallowing real work.
        assert any("Transaction 1 deleted" in r.message for r in caplog.records)

    async def test_missing_transaction_still_retries(self, consumer, monkeypatch) -> None:
        """The other control, and the one that proves we split the branch
        rather than closed it: an id that never existed must still back off
        and raise, so the retry ladder (and eventually the DLQ) is intact.
        """
        from app.workers.categorized_consumer import _TransactionNotFoundYet

        backoff = AsyncMock()
        monkeypatch.setattr(consumer, "_stale_backoff", backoff)

        msg = self._msg(999_999)
        payload = json.loads(msg.body)

        with pytest.raises(_TransactionNotFoundYet):
            await consumer.handle(payload, msg)

        backoff.assert_awaited_once()

    async def test_live_transaction_is_still_categorized(self, consumer, session_factory) -> None:
        """The third branch, unchanged — guards against the new check
        accidentally matching a live row (e.g. ``is not None`` inverted)."""
        from app.models import TransactionModel

        await consumer._on_message(self._msg(1))

        async with session_factory() as session:
            tx = (await session.execute(select(TransactionModel).where(TransactionModel.id == 1))).scalar_one()
            assert tx.subcategory_id == 7
