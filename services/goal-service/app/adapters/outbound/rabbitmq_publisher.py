from __future__ import annotations

import logging

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange
from contracts.base import BaseEvent

from app.application.ports.outbound import IEventPublisher

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "finans_tracker.events"


class RabbitMQPublisher(IEventPublisher):
    def __init__(self, rabbitmq_url: str) -> None:
        self._url = rabbitmq_url
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("Connected to RabbitMQ, exchange=%s", EXCHANGE_NAME)

    async def publish(self, event: BaseEvent) -> None:
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

    async def publish_raw(self, message: Message, routing_key: str) -> None:
        if self._exchange is None:
            raise RuntimeError("RabbitMQPublisher is not connected")
        await self._exchange.publish(message, routing_key=routing_key)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")
