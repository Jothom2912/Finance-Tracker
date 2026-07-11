"""RabbitMQ topic-exchange publisher.

Drop-in replacement for the per-service
``app/adapters/outbound/rabbitmq_publisher.py`` copies.  Semantics are
identical: durable topic exchange, persistent JSON messages, routing key
= ``event_type``.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

logger = logging.getLogger(__name__)

#: The single project-wide topic exchange for domain events.
EXCHANGE_NAME = "finans_tracker.events"


@runtime_checkable
class SerializableEvent(Protocol):
    """Structural type matched by ``contracts.base.BaseEvent``.

    Declared as a Protocol so this package has no hard dependency on
    ``finans-tracker-contracts`` — any object with ``event_type``,
    ``correlation_id`` and ``to_json()`` publishes fine.
    """

    event_type: str
    correlation_id: str

    def to_json(self) -> str: ...


class RabbitMQPublisher:
    """Publishes events to the durable topic exchange."""

    def __init__(self, rabbitmq_url: str, exchange_name: str = EXCHANGE_NAME) -> None:
        self._url = rabbitmq_url
        self._exchange_name = exchange_name
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("Connected to RabbitMQ, exchange=%s", self._exchange_name)

    async def publish(self, event: SerializableEvent) -> None:
        if self._exchange is None:
            raise RuntimeError("RabbitMQPublisher is not connected")

        message = Message(
            body=event.to_json().encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._exchange.publish(
            message,
            routing_key=event.event_type,
        )
        logger.info(
            "Published event %s (correlation_id=%s)",
            event.event_type,
            event.correlation_id,
        )

    async def publish_raw(self, message: Message, routing_key: str) -> None:
        """Publish a pre-built message (used by the outbox worker)."""
        if self._exchange is None:
            raise RuntimeError("RabbitMQPublisher is not connected")
        await self._exchange.publish(message, routing_key=routing_key)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")
