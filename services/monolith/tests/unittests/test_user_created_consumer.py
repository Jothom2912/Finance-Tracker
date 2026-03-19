from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.account.domain.entities import Account
from backend.consumers.base import HEADER_RETRY_COUNT, BaseConsumer
from backend.consumers.user_created import UserCreatedConsumer
from backend.models.mysql.processed_event import ProcessedEvent
from contracts.events.account import (
    AccountCreatedEvent,
    AccountCreationFailedEvent,
)


def _valid_event_data(
    user_id: int = 1,
    correlation_id: str = "corr-001",
) -> dict:
    return {
        "event_type": "user.created",
        "event_version": 1,
        "user_id": user_id,
        "email": "alice@example.com",
        "username": "alice",
        "correlation_id": correlation_id,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }


def _make_consumer(
    session_factory: MagicMock | None = None,
    publisher: AsyncMock | None = None,
) -> UserCreatedConsumer:
    return UserCreatedConsumer(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        db_session_factory=session_factory or MagicMock(),
        publisher=publisher or AsyncMock(),
    )


# ── UserCreatedConsumer.handle ──────────────────────────────────────


class TestUserCreatedHandle:
    @pytest.mark.asyncio()
    async def test_creates_default_account(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        publisher = AsyncMock()

        created_account = Account(id=10, name="Default Account", saldo=0.0, user_id=1)

        consumer = _make_consumer(factory, publisher)

        with patch("backend.consumers.user_created.MySQLAccountRepository") as mock_repo_cls:
            mock_repo_cls.return_value.create.return_value = created_account
            await consumer.handle(_valid_event_data())

        mock_repo_cls.return_value.create.assert_called_once()
        call_arg = mock_repo_cls.return_value.create.call_args[0][0]
        assert call_arg.name == "Default Account"
        assert call_arg.user_id == 1

    @pytest.mark.asyncio()
    async def test_publishes_account_created_event(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        publisher = AsyncMock()

        created_account = Account(id=10, name="Default Account", saldo=0.0, user_id=1)
        consumer = _make_consumer(factory, publisher)

        with patch("backend.consumers.user_created.MySQLAccountRepository") as mock_repo_cls:
            mock_repo_cls.return_value.create.return_value = created_account
            await consumer.handle(_valid_event_data())

        assert publisher.publish.await_count == 1
        event = publisher.publish.call_args[0][0]
        assert isinstance(event, AccountCreatedEvent)
        assert event.account_id == 10
        assert event.user_id == 1
        assert event.account_name == "Default Account"

    @pytest.mark.asyncio()
    async def test_propagates_correlation_id(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        publisher = AsyncMock()

        created_account = Account(id=10, name="Default Account", saldo=0.0, user_id=1)
        consumer = _make_consumer(factory, publisher)

        with patch("backend.consumers.user_created.MySQLAccountRepository") as mock_repo_cls:
            mock_repo_cls.return_value.create.return_value = created_account
            await consumer.handle(_valid_event_data(correlation_id="trace-abc-123"))

        event = publisher.publish.call_args[0][0]
        assert event.correlation_id == "trace-abc-123"

    @pytest.mark.asyncio()
    async def test_failure_publishes_compensation_event(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        publisher = AsyncMock()

        consumer = _make_consumer(factory, publisher)

        with patch("backend.consumers.user_created.MySQLAccountRepository") as mock_repo_cls:
            mock_repo_cls.return_value.create.side_effect = RuntimeError("DB down")
            with pytest.raises(RuntimeError):
                await consumer.handle(_valid_event_data())

        event = publisher.publish.call_args[0][0]
        assert isinstance(event, AccountCreationFailedEvent)
        assert event.user_id == 1
        assert "DB down" in event.reason

    @pytest.mark.asyncio()
    async def test_failure_reraises_for_retry(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        publisher = AsyncMock()

        consumer = _make_consumer(factory, publisher)

        with patch("backend.consumers.user_created.MySQLAccountRepository") as mock_repo_cls:
            mock_repo_cls.return_value.create.side_effect = RuntimeError("fail")
            with pytest.raises(RuntimeError, match="fail"):
                await consumer.handle(_valid_event_data())


# ── BaseConsumer idempotency (DB-backed) ───────────────────────────


@pytest.fixture()
def idempotency_db():
    """In-memory SQLite with only the processed_events table for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ProcessedEvent.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    return factory


class _StubConsumer(BaseConsumer):
    """Minimal subclass for testing base consumer behaviour."""

    def __init__(self, db_session_factory: object) -> None:
        super().__init__(
            rabbitmq_url="amqp://localhost",
            queue_name="test.queue",
            routing_key="test.event",
            db_session_factory=db_session_factory,
        )
        self.call_count = 0

    async def handle(self, event_data: dict[str, object]) -> None:
        self.call_count += 1


class _FailingConsumer(BaseConsumer):
    """Always-failing subclass for retry tests."""

    def __init__(self, db_session_factory: object) -> None:
        super().__init__(
            rabbitmq_url="amqp://localhost",
            queue_name="test.queue",
            routing_key="test.event",
            db_session_factory=db_session_factory,
            max_retries=2,
        )

    async def handle(self, event_data: dict[str, object]) -> None:
        raise RuntimeError("boom")


def _make_message(body: dict, retry_count: int | None = None) -> MagicMock:
    msg = MagicMock()
    msg.body = json.dumps(body).encode("utf-8")
    msg.headers = {}
    if retry_count is not None:
        msg.headers[HEADER_RETRY_COUNT] = retry_count
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()
    return msg


class TestIdempotency:
    @pytest.mark.asyncio()
    async def test_skips_duplicate(self, idempotency_db) -> None:
        consumer = _StubConsumer(idempotency_db)
        msg = _make_message({"correlation_id": "dup-1", "event_type": "test.event"})

        await consumer._on_message(msg)
        await consumer._on_message(msg)

        assert consumer.call_count == 1

    @pytest.mark.asyncio()
    async def test_allows_different_events(self, idempotency_db) -> None:
        consumer = _StubConsumer(idempotency_db)
        msg_a = _make_message({"correlation_id": "id-a", "event_type": "test.event"})
        msg_b = _make_message({"correlation_id": "id-b", "event_type": "test.event"})

        await consumer._on_message(msg_a)
        await consumer._on_message(msg_b)

        assert consumer.call_count == 2


class TestRetryLogic:
    @pytest.mark.asyncio()
    async def test_retry_increments_count(self, idempotency_db) -> None:
        consumer = _FailingConsumer(idempotency_db)
        consumer._exchange = AsyncMock()
        consumer._channel = AsyncMock()

        msg = _make_message({"correlation_id": "retry-1", "event_type": "test.event"}, retry_count=0)

        await consumer._on_message(msg)

        consumer._exchange.publish.assert_awaited_once()
        published_msg = consumer._exchange.publish.call_args[0][0]
        assert published_msg.headers[HEADER_RETRY_COUNT] == 1
        msg.ack.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_max_retries_sends_to_dlq(self, idempotency_db) -> None:
        consumer = _FailingConsumer(idempotency_db)
        consumer._exchange = AsyncMock()
        consumer._channel = AsyncMock()

        msg = _make_message({"correlation_id": "dlq-1", "event_type": "test.event"}, retry_count=2)

        await consumer._on_message(msg)

        msg.nack.assert_awaited_once_with(requeue=False)
        consumer._exchange.publish.assert_not_awaited()
