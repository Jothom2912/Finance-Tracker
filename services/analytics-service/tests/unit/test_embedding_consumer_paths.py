"""Beskedsti-tests for EmbeddingConsumer._on_message (uden RabbitMQ/ES/Ollama)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.application.embedding_projection import StaleProjectionError
from app.workers.embedding_consumer import MAX_RETRIES, QUEUE_NAME, EmbeddingConsumer
from contracts.events.transaction import TransactionCreatedEvent


def make_message(body: bytes, routing_key: str = "transaction.created", retry_count: int | None = None) -> AsyncMock:
    message = AsyncMock()
    message.body = body
    message.routing_key = routing_key
    message.headers = {"x-retry-count": retry_count} if retry_count is not None else {}
    return message


def make_consumer(handler: AsyncMock) -> EmbeddingConsumer:
    projector = AsyncMock()
    projector.handle = handler
    return EmbeddingConsumer(projector)


def valid_body(**overrides: Any) -> bytes:
    event = TransactionCreatedEvent(
        transaction_id=42,
        account_id=1,
        user_id=7,
        amount="-100.00",
        transaction_type="expense",
        tx_date="2026-04-15",
        **overrides,
    )
    return event.to_json().encode()


async def test_valid_event_is_handled_and_acked() -> None:
    handler = AsyncMock()
    consumer = make_consumer(handler)
    message = make_message(valid_body())

    await consumer._on_message(message)

    handler.assert_awaited_once()
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()


async def test_deleted_event_is_ignored() -> None:
    handler = AsyncMock()
    consumer = make_consumer(handler)
    body = json.dumps({"event_type": "transaction.deleted", "transaction_id": 42}).encode()
    message = make_message(body, routing_key="transaction.deleted")

    await consumer._on_message(message)

    handler.assert_not_awaited()
    message.ack.assert_awaited_once()


async def test_unparseable_body_goes_to_dlq() -> None:
    consumer = make_consumer(AsyncMock())
    message = make_message(b"ikke json")

    await consumer._on_message(message)

    message.nack.assert_awaited_once_with(requeue=False)


async def test_stale_projection_republishes_to_own_queue_not_topic_exchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry må ikke fan-oute til andre transaction.*-bundne køer."""
    monkeypatch.setattr("app.workers.embedding_consumer.STALE_RETRY_BACKOFF_S", 0.0)
    handler = AsyncMock(side_effect=StaleProjectionError("ikke projiceret endnu"))
    consumer = make_consumer(handler)
    consumer._channel = AsyncMock()
    message = make_message(valid_body())

    await consumer._on_message(message)

    publish = consumer._channel.default_exchange.publish
    publish.assert_awaited_once()
    assert publish.await_args.kwargs["routing_key"] == QUEUE_NAME
    assert publish.await_args.args[0].headers["x-retry-count"] == 1
    consumer._channel.declare_exchange.assert_not_awaited()
    message.ack.assert_awaited_once()


async def test_failure_at_max_retries_goes_to_dlq() -> None:
    handler = AsyncMock(side_effect=RuntimeError("Ollama nede"))
    consumer = make_consumer(handler)
    message = make_message(valid_body(), retry_count=MAX_RETRIES)

    await consumer._on_message(message)

    message.nack.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()
