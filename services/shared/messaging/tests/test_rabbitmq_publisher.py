"""RabbitMQPublisher unit tests with a mocked exchange."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from aio_pika import DeliveryMode, Message
from messaging.rabbitmq import EXCHANGE_NAME, RabbitMQPublisher

from tests.conftest import FakeEvent


def test_exchange_name_constant() -> None:
    assert EXCHANGE_NAME == "finans_tracker.events"


class TestNotConnected:
    async def test_publish_raises(self) -> None:
        publisher = RabbitMQPublisher("amqp://test")
        with pytest.raises(RuntimeError, match="not connected"):
            await publisher.publish(FakeEvent())

    async def test_publish_raw_raises(self) -> None:
        publisher = RabbitMQPublisher("amqp://test")
        with pytest.raises(RuntimeError, match="not connected"):
            await publisher.publish_raw(Message(body=b"{}"), routing_key="x.y")


class TestPublish:
    def _connected(self) -> RabbitMQPublisher:
        publisher = RabbitMQPublisher("amqp://test")
        publisher._exchange = AsyncMock()
        return publisher

    async def test_publish_routes_by_event_type_with_persistent_json(self) -> None:
        publisher = self._connected()
        event = FakeEvent("user.created", user_id=1)

        await publisher.publish(event)

        publisher._exchange.publish.assert_awaited_once()
        args, kwargs = publisher._exchange.publish.await_args
        message = args[0]
        assert kwargs["routing_key"] == "user.created"
        assert message.delivery_mode == DeliveryMode.PERSISTENT
        assert message.content_type == "application/json"
        assert json.loads(message.body) == json.loads(event.to_json())

    async def test_publish_raw_forwards_message_and_routing_key(self) -> None:
        publisher = self._connected()
        message = Message(body=b'{"k": 1}')

        await publisher.publish_raw(message, routing_key="a.b")

        publisher._exchange.publish.assert_awaited_once_with(
            message, routing_key="a.b"
        )

    async def test_close_without_connection_is_noop(self) -> None:
        publisher = RabbitMQPublisher("amqp://test")
        await publisher.close()  # must not raise
