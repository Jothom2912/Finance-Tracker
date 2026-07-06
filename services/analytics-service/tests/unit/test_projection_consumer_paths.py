"""Beskedsti-tests for ProjectionConsumer._on_message (uden RabbitMQ/ES)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.workers.projection_consumer import MAX_RETRIES, ProjectionConsumer
from contracts.events.goal import GoalDeletedEvent


def make_message(body: bytes, routing_key: str = "goal.deleted", retry_count: int | None = None) -> AsyncMock:
    message = AsyncMock()
    message.body = body
    message.routing_key = routing_key
    message.headers = {"x-retry-count": retry_count} if retry_count is not None else {}
    return message


def make_consumer(handler: Any) -> ProjectionConsumer:
    return ProjectionConsumer({"goal.deleted": (GoalDeletedEvent, handler)})


def valid_body(**overrides: Any) -> bytes:
    event = GoalDeletedEvent(goal_id=1, user_id=7, **overrides)
    return event.to_json().encode()


async def test_valid_event_is_handled_and_acked() -> None:
    handler = AsyncMock()
    consumer = make_consumer(handler)
    message = make_message(valid_body())

    await consumer._on_message(message)

    handler.assert_awaited_once()
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()


async def test_unparseable_body_goes_to_dlq() -> None:
    handler = AsyncMock()
    consumer = make_consumer(handler)
    message = make_message(b"ikke json")

    await consumer._on_message(message)

    handler.assert_not_awaited()
    message.nack.assert_awaited_once_with(requeue=False)


async def test_invalid_payload_goes_to_dlq() -> None:
    handler = AsyncMock()
    consumer = make_consumer(handler)
    body = json.dumps({"event_type": "goal.deleted", "goal_id": "ikke-et-tal"}).encode()
    message = make_message(body)

    await consumer._on_message(message)

    handler.assert_not_awaited()
    message.nack.assert_awaited_once_with(requeue=False)


async def test_unknown_event_type_is_acked_and_ignored() -> None:
    handler = AsyncMock()
    consumer = make_consumer(handler)
    body = json.dumps({"event_type": "account.creation_failed", "user_id": 1}).encode()
    message = make_message(body, routing_key="account.creation_failed")

    await consumer._on_message(message)

    handler.assert_not_awaited()
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()


async def test_handler_failure_below_max_retries_republishes_and_acks() -> None:
    handler = AsyncMock(side_effect=RuntimeError("ES nede"))
    consumer = make_consumer(handler)
    consumer._channel = AsyncMock()
    exchange = AsyncMock()
    consumer._channel.declare_exchange.return_value = exchange
    message = make_message(valid_body(), retry_count=1)

    await consumer._on_message(message)

    exchange.publish.assert_awaited_once()
    published = exchange.publish.await_args
    assert published.kwargs["routing_key"] == "goal.deleted"
    assert published.args[0].headers["x-retry-count"] == 2
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()


async def test_handler_failure_at_max_retries_goes_to_dlq() -> None:
    handler = AsyncMock(side_effect=RuntimeError("ES nede"))
    consumer = make_consumer(handler)
    message = make_message(valid_body(), retry_count=MAX_RETRIES)

    await consumer._on_message(message)

    message.nack.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


@pytest.mark.parametrize("missing_headers", [None, {}])
async def test_missing_retry_header_treated_as_zero(missing_headers: Any) -> None:
    handler = AsyncMock(side_effect=RuntimeError("ES nede"))
    consumer = make_consumer(handler)
    consumer._channel = AsyncMock()
    exchange = AsyncMock()
    consumer._channel.declare_exchange.return_value = exchange
    message = make_message(valid_body())
    message.headers = missing_headers

    await consumer._on_message(message)

    assert exchange.publish.await_args.args[0].headers["x-retry-count"] == 1
    message.ack.assert_awaited_once()
