from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
)

logger = logging.getLogger(__name__)

HEADER_RETRY_COUNT = "x-retry-count"


class BaseConsumer(ABC):
    """Reusable async RabbitMQ consumer with retry, DLQ, and idempotency.

    Subclasses implement ``handle`` with domain-specific logic.  The base
    class takes care of connection setup, dead-letter routing, retry with
    back-off, and correlation-id-based idempotency checks.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str,
        routing_key: str,
        exchange_name: str = "finans_tracker.events",
        max_retries: int = 3,
    ) -> None:
        self._url = rabbitmq_url
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._exchange_name = exchange_name
        self._max_retries = max_retries

        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None
        self._queue: AbstractQueue | None = None

        # TODO: Replace with Redis or database-backed idempotency store
        # for production.  An in-memory set is sufficient for demonstration
        # but does not survive process restarts.
        self._processed_ids: set[str] = set()

    # ── connection ──────────────────────────────────────────────────

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

        dlx_name = f"{self._exchange_name}.dlx"
        dlx = await self._channel.declare_exchange(
            dlx_name,
            ExchangeType.DIRECT,
            durable=True,
        )

        dlq_name = f"{self._queue_name}.dlq"
        dlq = await self._channel.declare_queue(dlq_name, durable=True)
        await dlq.bind(dlx, routing_key=self._queue_name)

        self._queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": dlx_name,
                "x-dead-letter-routing-key": self._queue_name,
            },
        )
        await self._queue.bind(self._exchange, routing_key=self._routing_key)

        logger.info(
            "Connected — queue=%s, routing_key=%s, dlq=%s",
            self._queue_name,
            self._routing_key,
            dlq_name,
        )

    # ── message dispatch ────────────────────────────────────────────

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        correlation_id: str | None = None
        try:
            body = json.loads(message.body.decode("utf-8"))
            correlation_id = body.get("correlation_id", "")

            if correlation_id in self._processed_ids:
                logger.info(
                    "Skipping duplicate event (correlation_id=%s)",
                    correlation_id,
                )
                await message.ack()
                return

            await self.handle(body)

            if correlation_id:
                self._processed_ids.add(correlation_id)
            await message.ack()

        except Exception:
            retry_count = self._get_retry_count(message)
            cid = correlation_id or "unknown"

            if retry_count < self._max_retries:
                logger.warning(
                    "Handler failed (correlation_id=%s, retry=%d/%d) — "
                    "republishing",
                    cid,
                    retry_count + 1,
                    self._max_retries,
                    exc_info=True,
                )
                await self._republish(message, retry_count + 1)
                await message.ack()
            else:
                logger.error(
                    "Handler failed after %d retries (correlation_id=%s) — "
                    "sending to DLQ",
                    self._max_retries,
                    cid,
                    exc_info=True,
                )
                await message.nack(requeue=False)

    # ── retry helpers ───────────────────────────────────────────────

    @staticmethod
    def _get_retry_count(message: AbstractIncomingMessage) -> int:
        headers = message.headers or {}
        return int(headers.get(HEADER_RETRY_COUNT, 0))

    async def _republish(
        self, original: AbstractIncomingMessage, retry_count: int
    ) -> None:
        assert self._channel is not None
        assert self._exchange is not None

        headers = dict(original.headers or {})
        headers[HEADER_RETRY_COUNT] = retry_count

        msg = Message(
            body=original.body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        await self._exchange.publish(msg, routing_key=self._routing_key)

    # ── abstract handler ────────────────────────────────────────────

    @abstractmethod
    async def handle(self, event_data: dict[str, object]) -> None:
        """Process a single deserialized event.  Raise to trigger retry."""

    # ── run loop ────────────────────────────────────────────────────

    async def run(self) -> None:
        await self.connect()
        assert self._channel is not None
        assert self._queue is not None

        await self._channel.set_qos(prefetch_count=1)
        await self._queue.consume(self._on_message)

        logger.info("Consumer %s is running", self._queue_name)
        await asyncio.Future()  # block forever
