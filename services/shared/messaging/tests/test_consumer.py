"""ConsumerBase retry/DLQ/poison/dedup paths with mocked aio_pika objects.

Mock patterns follow
``services/account-service/tests/unit/test_account_creation_consumer.py``:
the consumer is exercised directly via ``_on_message`` — no broker.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aio_pika.abc import AbstractIncomingMessage
from messaging.consumer import (
    RETRY_HEADER,
    ConsumerBase,
    PoisonMessageError,
)

QUEUE_NAME = "test_service.thing"
MAX_RETRIES = 3


class RecordingConsumer(ConsumerBase):
    """Test consumer: records payloads, raises what it's told to."""

    def __init__(self, *, error: Exception | None = None, **kwargs: Any) -> None:
        super().__init__(
            "amqp://test",
            QUEUE_NAME,
            "thing.happened",
            max_retries=MAX_RETRIES,
            **kwargs,
        )
        self.error = error
        self.handled: list[dict[str, Any]] = []

    async def handle(
        self, payload: dict[str, Any], message: AbstractIncomingMessage
    ) -> None:
        if self.error is not None:
            raise self.error
        self.handled.append(payload)


def _make_consumer(**kwargs: Any) -> RecordingConsumer:
    consumer = RecordingConsumer(**kwargs)
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


class TestHappyPath:
    async def test_success_acks_without_republish(self) -> None:
        consumer = _make_consumer()
        message = _make_message({"event_type": "thing.happened", "value": 1})

        await consumer._on_message(message)

        assert consumer.handled == [{"event_type": "thing.happened", "value": 1}]
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()
        consumer._channel.default_exchange.publish.assert_not_awaited()


class TestPoisonMessages:
    async def test_invalid_json_goes_straight_to_dlq(self) -> None:
        consumer = _make_consumer()
        message = _make_message(b"not json")

        await consumer._on_message(message)

        assert consumer.handled == []
        message.nack.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()

    async def test_non_object_payload_goes_to_dlq(self) -> None:
        consumer = _make_consumer()
        message = _make_message(b"[1, 2, 3]")

        await consumer._on_message(message)

        assert consumer.handled == []
        message.nack.assert_awaited_once_with(requeue=False)

    async def test_poison_message_error_skips_retries(self) -> None:
        consumer = _make_consumer(error=PoisonMessageError("schema mismatch"))
        message = _make_message({"event_type": "thing.happened"})

        await consumer._on_message(message)

        message.nack.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()
        consumer._channel.default_exchange.publish.assert_not_awaited()


class TestRetry:
    async def test_failure_republishes_to_own_queue_with_incremented_header(self) -> None:
        consumer = _make_consumer(error=RuntimeError("db down"))
        message = _make_message({"event_type": "thing.happened", "correlation_id": "c-1"})

        await consumer._on_message(message)

        publish = consumer._channel.default_exchange.publish
        publish.assert_awaited_once()
        args, kwargs = publish.await_args
        # Republished to the consumer's OWN queue via the default exchange —
        # never back to the topic exchange (would fan out to other consumers).
        assert kwargs["routing_key"] == QUEUE_NAME
        assert args[0].headers[RETRY_HEADER] == 1
        assert args[0].body == message.body
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()

    async def test_existing_retry_header_is_incremented(self) -> None:
        consumer = _make_consumer(error=RuntimeError("db down"))
        message = _make_message(
            {"event_type": "thing.happened"}, headers={RETRY_HEADER: 1}
        )

        await consumer._on_message(message)

        args, _ = consumer._channel.default_exchange.publish.await_args
        assert args[0].headers[RETRY_HEADER] == 2

    async def test_failure_after_max_retries_goes_to_dlq(self) -> None:
        consumer = _make_consumer(error=RuntimeError("db down"))
        message = _make_message(
            {"event_type": "thing.happened"}, headers={RETRY_HEADER: MAX_RETRIES}
        )

        await consumer._on_message(message)

        message.nack.assert_awaited_once_with(requeue=False)
        message.ack.assert_not_awaited()
        consumer._channel.default_exchange.publish.assert_not_awaited()

    async def test_republish_failure_nacks_with_requeue(self) -> None:
        consumer = _make_consumer(error=RuntimeError("db down"))
        consumer._channel.default_exchange.publish = AsyncMock(
            side_effect=ConnectionError("channel gone")
        )
        message = _make_message({"event_type": "thing.happened"})

        await consumer._on_message(message)

        # Message must not be lost: requeued for redelivery
        message.nack.assert_awaited_once_with(requeue=True)
        message.ack.assert_not_awaited()


class FakeDedup:
    def __init__(self, seen: set[str] | None = None) -> None:
        self.seen = seen or set()
        self.marked: list[tuple[str, str]] = []

    async def already_processed(self, message_id: str, event_type: str) -> bool:
        return message_id in self.seen

    async def mark_processed(self, message_id: str, event_type: str) -> None:
        self.marked.append((message_id, event_type))


class TestInboxDedup:
    async def test_duplicate_is_acked_without_handling(self) -> None:
        dedup = FakeDedup(seen={"c-42"})
        consumer = _make_consumer(deduplicator=dedup)
        message = _make_message(
            {"event_type": "thing.happened", "correlation_id": "c-42"}
        )

        await consumer._on_message(message)

        assert consumer.handled == []
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()
        assert dedup.marked == []

    async def test_fresh_message_is_handled_and_marked(self) -> None:
        dedup = FakeDedup()
        consumer = _make_consumer(deduplicator=dedup)
        message = _make_message(
            {"event_type": "thing.happened", "correlation_id": "c-7"}
        )

        await consumer._on_message(message)

        assert len(consumer.handled) == 1
        assert dedup.marked == [("c-7", "thing.happened")]
        message.ack.assert_awaited_once()

    async def test_message_without_correlation_id_skips_dedup(self) -> None:
        dedup = FakeDedup()
        consumer = _make_consumer(deduplicator=dedup)
        message = _make_message({"event_type": "thing.happened"})

        await consumer._on_message(message)

        assert len(consumer.handled) == 1
        assert dedup.marked == []
        message.ack.assert_awaited_once()


class TestShutdown:
    async def test_stop_unblocks_run(self) -> None:
        consumer = _make_consumer()
        # Simulate run() waiting on the stop event without a broker
        consumer._stopped.clear()
        await consumer.stop()
        assert consumer._stopped.is_set()
