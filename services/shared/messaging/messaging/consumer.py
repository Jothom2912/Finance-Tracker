"""RabbitMQ consumer base class with DLQ + header-based retry.

Consolidates the per-service consumer boilerplate.  Topology and
semantics follow the two best existing implementations:

* Queue/DLX/DLQ declaration mirrors
  ``goal-service/app/workers/budget_month_closed_consumer.py``:
  durable topic exchange, direct DLX ``<exchange>.dlx``, DLQ
  ``<queue>.dlq`` bound with routing key = queue name, main queue
  declared with ``x-dead-letter-exchange`` / ``x-dead-letter-routing-key``.
* Retry mirrors ``account-service/app/consumers/account_creation_consumer.py``
  (the fixed variant): failed messages are republished to the consumer's
  OWN queue via the default exchange with an incremented ``x-retry-count``
  header — NOT to the topic exchange, which would re-deliver the event to
  every other bound consumer (goal-service's remaining bug).

Poison messages (unparseable JSON, non-object payloads, or handler
raising :class:`PoisonMessageError`) are nacked without requeue and land
in the DLQ immediately — no retries.

Idempotency: delivery is at-least-once.  Pass a ``deduplicator``
implementing :class:`InboxDeduplicator` (``processed_events``-style
inbox) for a fast-path duplicate skip.  For strict once-only effects the
handler should additionally record the idempotency key inside its own
database transaction.

Subclass contract::

    class MyConsumer(ConsumerBase):
        async def handle(self, payload: dict[str, Any],
                         message: AbstractIncomingMessage) -> None:
            ...  # raise PoisonMessageError for unrecoverable payloads
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol, Sequence

import aio_pika
from aio_pika import DeliveryMode, ExchangeType
from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractRobustConnection,
)

from messaging.rabbitmq import EXCHANGE_NAME

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_PREFETCH_COUNT = 1
RETRY_HEADER = "x-retry-count"


class PoisonMessageError(Exception):
    """Raise from ``handle`` for unrecoverable payloads → straight to DLQ."""


class InboxDeduplicator(Protocol):
    """Inbox-pattern hook (``processed_events``-style).

    ``message_id`` is the event's ``correlation_id`` (per-event UUID),
    matching the existing ``processed_events.message_id`` convention.
    """

    async def already_processed(self, message_id: str, event_type: str) -> bool: ...

    async def mark_processed(self, message_id: str, event_type: str) -> None: ...


class ConsumerBase:
    """Connection/topology/retry boilerplate; subclasses implement ``handle``."""

    def __init__(
        self,
        rabbitmq_url: str,
        queue_name: str,
        routing_keys: str | Sequence[str],
        *,
        exchange_name: str = EXCHANGE_NAME,
        max_retries: int = DEFAULT_MAX_RETRIES,
        prefetch_count: int = DEFAULT_PREFETCH_COUNT,
        deduplicator: InboxDeduplicator | None = None,
    ) -> None:
        self._rabbitmq_url = rabbitmq_url
        self._queue_name = queue_name
        self._routing_keys: tuple[str, ...] = (routing_keys,) if isinstance(routing_keys, str) else tuple(routing_keys)
        self._exchange_name = exchange_name
        self._max_retries = max_retries
        self._prefetch_count = prefetch_count
        self._dedup = deduplicator
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._stopped = asyncio.Event()

    async def handle(
        self,
        payload: dict[str, Any],
        message: AbstractIncomingMessage,
    ) -> None:
        """Process one parsed message.  Must be overridden.

        Raise :class:`PoisonMessageError` for unrecoverable payloads
        (schema validation failures) — any other exception triggers the
        retry/DLQ ladder.
        """
        raise NotImplementedError

    async def run(self) -> None:
        """Declare topology, consume until :meth:`stop` is called."""
        self._stopped.clear()
        self._connection = await aio_pika.connect_robust(self._rabbitmq_url)
        try:
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self._prefetch_count)

            queue = await self._declare_topology(self._channel)
            await queue.consume(self._on_message)

            logger.info(
                "Consumer %s listening on %s (exchange=%s)",
                self._queue_name,
                ", ".join(self._routing_keys),
                self._exchange_name,
            )
            await self._stopped.wait()
        finally:
            await self._connection.close()
            logger.info("Consumer %s stopped", self._queue_name)

    async def stop(self) -> None:
        """Request a graceful shutdown of :meth:`run`."""
        self._stopped.set()

    async def _declare_topology(self, channel: AbstractChannel) -> Any:
        exchange = await channel.declare_exchange(
            self._exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

        dlx = await channel.declare_exchange(
            f"{self._exchange_name}.dlx",
            ExchangeType.DIRECT,
            durable=True,
        )
        dlq = await channel.declare_queue(f"{self._queue_name}.dlq", durable=True)
        await dlq.bind(dlx, routing_key=self._queue_name)

        # NOTE (deploy): if the queue already exists WITHOUT dead-letter
        # arguments, RabbitMQ rejects this declaration (PRECONDITION_FAILED).
        # The old queue must be drained and deleted once — see MIGRATION.md.
        queue = await channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{self._exchange_name}.dlx",
                "x-dead-letter-routing-key": self._queue_name,
            },
        )
        for routing_key in self._routing_keys:
            await queue.bind(exchange, routing_key=routing_key)
        return queue

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        # JSON parsing sits inside its own error handling: a malformed
        # body can never crash the consumer — it is dead-lettered.
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except Exception:
            logger.error(
                "Invalid JSON on %s — sending to DLQ",
                self._queue_name,
                exc_info=True,
            )
            await message.nack(requeue=False)
            return

        if not isinstance(payload, dict):
            logger.error(
                "Non-object payload on %s (%s) — sending to DLQ",
                self._queue_name,
                type(payload).__name__,
            )
            await message.nack(requeue=False)
            return

        correlation_id = payload.get("correlation_id")
        event_type = str(payload.get("event_type", ""))

        try:
            if self._dedup is not None and correlation_id:
                if await self._dedup.already_processed(str(correlation_id), event_type):
                    logger.info(
                        "Duplicate %s (correlation_id=%s) — acking without handling",
                        event_type or "message",
                        correlation_id,
                    )
                    await message.ack()
                    return

            await self.handle(payload, message)

            if self._dedup is not None and correlation_id:
                await self._dedup.mark_processed(str(correlation_id), event_type)

            await message.ack()

        except PoisonMessageError:
            logger.error(
                "Unrecoverable message on %s (correlation_id=%s) — sending to DLQ",
                self._queue_name,
                correlation_id,
                exc_info=True,
            )
            await message.nack(requeue=False)

        except Exception:
            retry_count = int((message.headers or {}).get(RETRY_HEADER, 0))
            if retry_count < self._max_retries:
                logger.warning(
                    "Handler failed on %s (retry=%d/%d, correlation_id=%s) — republishing",
                    self._queue_name,
                    retry_count + 1,
                    self._max_retries,
                    correlation_id,
                    exc_info=True,
                )
                try:
                    await self._republish(message, retry_count + 1)
                except Exception:
                    logger.error(
                        "Republish on %s failed — nacking with requeue",
                        self._queue_name,
                        exc_info=True,
                    )
                    await message.nack(requeue=True)
                    return
                await message.ack()
            else:
                logger.error(
                    "Max retries reached on %s (correlation_id=%s) — sending to DLQ",
                    self._queue_name,
                    correlation_id,
                    exc_info=True,
                )
                await message.nack(requeue=False)

    async def _republish(
        self,
        original: AbstractIncomingMessage,
        retry_count: int,
    ) -> None:
        """Republish to our OWN queue via the default exchange.

        Publishing to the queue directly (instead of the topic exchange)
        avoids re-delivering the event to every other bound consumer.
        """
        assert self._channel is not None
        headers = dict(original.headers or {})
        headers[RETRY_HEADER] = retry_count
        msg = aio_pika.Message(
            body=original.body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=headers,
        )
        await self._channel.default_exchange.publish(msg, routing_key=self._queue_name)
