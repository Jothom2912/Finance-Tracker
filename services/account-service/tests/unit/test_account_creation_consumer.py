"""Unit tests for the retry/DLQ behaviour of AccountCreationConsumer.

The consumer is exercised directly via ``_on_message`` with mocked
aio_pika messages/channel — no RabbitMQ broker involved.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.consumers.account_creation_consumer import (
    MAX_RETRIES,
    QUEUE_NAME,
    AccountCreationConsumer,
)


def _make_consumer() -> AccountCreationConsumer:
    consumer = AccountCreationConsumer("amqp://test", session_factory=MagicMock())
    channel = MagicMock()
    channel.default_exchange.publish = AsyncMock()
    consumer._channel = channel
    return consumer


def _make_message(body: dict | bytes, headers: dict | None = None) -> MagicMock:
    message = MagicMock()
    message.body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    message.headers = headers or {}
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    return message


class TestAccountCreationConsumerRetry:
    def test_success_acks_without_republish(self):
        consumer = _make_consumer()
        message = _make_message({"user_id": 42})

        with patch.object(consumer, "_handle_user_created") as handle:
            asyncio.run(consumer._on_message(message))

        handle.assert_called_once_with(42)
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()
        consumer._channel.default_exchange.publish.assert_not_awaited()

    def test_failure_republishes_with_incremented_retry_header(self):
        consumer = _make_consumer()
        message = _make_message({"user_id": 42})

        with patch.object(consumer, "_handle_user_created", side_effect=RuntimeError("db down")):
            asyncio.run(consumer._on_message(message))

        publish = consumer._channel.default_exchange.publish
        publish.assert_awaited_once()
        republished, kwargs = publish.await_args
        assert kwargs["routing_key"] == QUEUE_NAME
        assert republished[0].headers["x-retry-count"] == 1
        assert republished[0].body == message.body
        # Republished copy replaces the original, which is acked (not nacked)
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()

    def test_failure_after_max_retries_goes_to_dlq(self):
        consumer = _make_consumer()
        message = _make_message({"user_id": 42}, headers={"x-retry-count": MAX_RETRIES})

        with patch.object(consumer, "_handle_user_created", side_effect=RuntimeError("db down")):
            asyncio.run(consumer._on_message(message))

        message.nack.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()
        consumer._channel.default_exchange.publish.assert_not_awaited()

    def test_invalid_payload_goes_straight_to_dlq(self):
        consumer = _make_consumer()
        message = _make_message(b"not json")

        with patch.object(consumer, "_handle_user_created") as handle:
            asyncio.run(consumer._on_message(message))

        handle.assert_not_called()
        message.nack.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()
