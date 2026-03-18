from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from contracts.events.account import (
    AccountCreatedEvent,
    AccountCreationFailedEvent,
)

from backend.account.domain.entities import Account
from backend.consumers.account_creation import AccountCreationConsumer
from backend.consumers.base import HEADER_RETRY_COUNT, BaseConsumer
from backend.consumers.user_sync import UserSyncConsumer


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


# ── AccountCreationConsumer ─────────────────────────────────────────


def _make_account_consumer(
    session_factory: MagicMock | None = None,
    publisher: AsyncMock | None = None,
) -> AccountCreationConsumer:
    return AccountCreationConsumer(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        db_session_factory=session_factory or MagicMock(),
        publisher=publisher or AsyncMock(),
    )


class TestAccountCreationConsumer:
    @pytest.mark.asyncio()
    async def test_uses_own_queue_name(self) -> None:
        consumer = _make_account_consumer()
        assert consumer._queue_name == "monolith.account_creation"

    @pytest.mark.asyncio()
    async def test_creates_default_account(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        publisher = AsyncMock()

        created_account = Account(id=10, name="Default Account", saldo=0.0, user_id=1)

        consumer = _make_account_consumer(factory, publisher)

        with patch("backend.consumers.account_creation.MySQLAccountRepository") as mock_repo_cls:
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
        consumer = _make_account_consumer(factory, publisher)

        with patch("backend.consumers.account_creation.MySQLAccountRepository") as mock_repo_cls:
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
        consumer = _make_account_consumer(factory, publisher)

        with patch("backend.consumers.account_creation.MySQLAccountRepository") as mock_repo_cls:
            mock_repo_cls.return_value.create.return_value = created_account
            await consumer.handle(_valid_event_data(correlation_id="trace-abc-123"))

        event = publisher.publish.call_args[0][0]
        assert event.correlation_id == "trace-abc-123"

    @pytest.mark.asyncio()
    async def test_failure_publishes_compensation_event(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=session)
        publisher = AsyncMock()

        consumer = _make_account_consumer(factory, publisher)

        with patch("backend.consumers.account_creation.MySQLAccountRepository") as mock_repo_cls:
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

        consumer = _make_account_consumer(factory, publisher)

        with patch("backend.consumers.account_creation.MySQLAccountRepository") as mock_repo_cls:
            mock_repo_cls.return_value.create.side_effect = RuntimeError("fail")
            with pytest.raises(RuntimeError, match="fail"):
                await consumer.handle(_valid_event_data())


# ── UserSyncConsumer ────────────────────────────────────────────────


def _make_sync_consumer(
    session_factory: MagicMock | None = None,
) -> UserSyncConsumer:
    return UserSyncConsumer(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        db_session_factory=session_factory or MagicMock(),
    )


class TestUserSyncConsumer:
    @pytest.mark.asyncio()
    async def test_uses_own_queue_name(self) -> None:
        consumer = _make_sync_consumer()
        assert consumer._queue_name == "monolith.user_sync"

    @pytest.mark.asyncio()
    async def test_creates_user_in_mysql(self) -> None:
        session = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = None
        session.query.return_value = query_mock

        factory = MagicMock(return_value=session)
        consumer = _make_sync_consumer(factory)

        await consumer.handle(_valid_event_data(user_id=42))

        session.add.assert_called_once()
        added_model = session.add.call_args[0][0]
        assert added_model.idUser == 42
        assert added_model.username == "alice"
        assert added_model.email == "alice@example.com"
        session.commit.assert_called_once()

    @pytest.mark.asyncio()
    async def test_skips_existing_user(self) -> None:
        session = MagicMock()
        existing_user = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = existing_user
        session.query.return_value = query_mock

        factory = MagicMock(return_value=session)
        consumer = _make_sync_consumer(factory)

        await consumer.handle(_valid_event_data(user_id=42))

        session.add.assert_not_called()
        session.commit.assert_not_called()

    @pytest.mark.asyncio()
    async def test_rollback_on_error(self) -> None:
        session = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = None
        session.query.return_value = query_mock
        session.commit.side_effect = RuntimeError("DB error")

        factory = MagicMock(return_value=session)
        consumer = _make_sync_consumer(factory)

        with pytest.raises(RuntimeError, match="DB error"):
            await consumer.handle(_valid_event_data())

        session.rollback.assert_called_once()
        session.close.assert_called_once()

    @pytest.mark.asyncio()
    async def test_always_closes_session(self) -> None:
        session = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = None
        session.query.return_value = query_mock

        factory = MagicMock(return_value=session)
        consumer = _make_sync_consumer(factory)

        await consumer.handle(_valid_event_data())

        session.close.assert_called_once()


# ── Consumers are independent ──────────────────────────────────────


class TestConsumerIndependence:
    """Both consumers listen on user.created but use different queues,
    so RabbitMQ delivers the event to both independently."""

    def test_different_queue_names(self) -> None:
        sync = _make_sync_consumer()
        account = _make_account_consumer()
        assert sync._queue_name != account._queue_name

    def test_same_routing_key(self) -> None:
        sync = _make_sync_consumer()
        account = _make_account_consumer()
        assert sync._routing_key == account._routing_key == "user.created"


# ── BaseConsumer idempotency (preserved from original tests) ────────


class _StubConsumer(BaseConsumer):
    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url="amqp://localhost",
            queue_name="test.queue",
            routing_key="test.event",
        )
        self.call_count = 0

    async def handle(self, event_data: dict[str, object]) -> None:
        self.call_count += 1


class _FailingConsumer(BaseConsumer):
    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url="amqp://localhost",
            queue_name="test.queue",
            routing_key="test.event",
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
    async def test_skips_duplicate(self) -> None:
        consumer = _StubConsumer()
        msg = _make_message({"correlation_id": "dup-1"})

        await consumer._on_message(msg)
        await consumer._on_message(msg)

        assert consumer.call_count == 1

    @pytest.mark.asyncio()
    async def test_allows_different_events(self) -> None:
        consumer = _StubConsumer()
        msg_a = _make_message({"correlation_id": "id-a"})
        msg_b = _make_message({"correlation_id": "id-b"})

        await consumer._on_message(msg_a)
        await consumer._on_message(msg_b)

        assert consumer.call_count == 2


class TestRetryLogic:
    @pytest.mark.asyncio()
    async def test_retry_increments_count(self) -> None:
        consumer = _FailingConsumer()
        consumer._exchange = AsyncMock()
        consumer._channel = AsyncMock()

        msg = _make_message({"correlation_id": "retry-1"}, retry_count=0)

        await consumer._on_message(msg)

        consumer._exchange.publish.assert_awaited_once()
        published_msg = consumer._exchange.publish.call_args[0][0]
        assert published_msg.headers[HEADER_RETRY_COUNT] == 1
        msg.ack.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_max_retries_sends_to_dlq(self) -> None:
        consumer = _FailingConsumer()
        consumer._exchange = AsyncMock()
        consumer._channel = AsyncMock()

        msg = _make_message({"correlation_id": "dlq-1"}, retry_count=2)

        await consumer._on_message(msg)

        msg.nack.assert_awaited_once_with(requeue=False)
        consumer._exchange.publish.assert_not_awaited()
