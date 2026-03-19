"""Standalone worker process that runs all RabbitMQ consumers.

Supports running individual consumers or all of them.

Usage::

    python -m backend.consumers.worker                    # all consumers
    python -m backend.consumers.worker --consumer user-sync
    python -m backend.consumers.worker --consumer account-creation

Or via uv::

    uv run python -m backend.consumers.worker
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from backend.config import DATABASE_URL, RABBITMQ_URL
from backend.consumers.account_creation import AccountCreationConsumer
from backend.consumers.category_sync import CategorySyncConsumer
from backend.consumers.user_sync import UserSyncConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


class _WorkerPublisher:
    """Lightweight ``IEventPublisher`` used by the consumer worker.

    Shares the same RabbitMQ connection / exchange as the consumer so
    outgoing saga events (``AccountCreatedEvent``, etc.) are published
    to the same ``finans_tracker.events`` topic exchange.
    """

    def __init__(self, rabbitmq_url: str) -> None:
        self._url = rabbitmq_url
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            "finans_tracker.events",
            ExchangeType.TOPIC,
            durable=True,
        )

    async def publish(self, event: object) -> None:
        if self._exchange is None:
            raise RuntimeError("Publisher not connected")

        msg = Message(
            body=event.to_json().encode("utf-8"),  # type: ignore[union-attr]
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._exchange.publish(
            msg,
            routing_key=event.event_type,  # type: ignore[union-attr]
        )

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()


def _build_session_factory():  # type: ignore[no-untyped-def]
    """Create a sync ``SessionLocal`` factory from the monolith DB url."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def _run_user_sync(session_factory: object) -> None:
    """Run only the user-sync consumer."""
    consumer = UserSyncConsumer(
        rabbitmq_url=RABBITMQ_URL,
        db_session_factory=session_factory,
    )
    await consumer.run()


async def _run_account_creation(session_factory: object, publisher: _WorkerPublisher) -> None:
    """Run only the account-creation consumer."""
    consumer = AccountCreationConsumer(
        rabbitmq_url=RABBITMQ_URL,
        db_session_factory=session_factory,
        publisher=publisher,
    )
    await consumer.run()


async def _run_category_sync(session_factory: object) -> None:
    """Run only the category-sync consumer."""
    consumer = CategorySyncConsumer(
        rabbitmq_url=RABBITMQ_URL,
        db_session_factory=session_factory,
    )
    await consumer.run()


async def main(consumer_name: str | None = None) -> None:
    logger.info("Starting consumer worker …")

    session_factory = _build_session_factory()

    publisher = _WorkerPublisher(RABBITMQ_URL)
    await publisher.connect()

    try:
        if consumer_name == "user-sync":
            logger.info("Running user-sync consumer only")
            await _run_user_sync(session_factory)
        elif consumer_name == "account-creation":
            logger.info("Running account-creation consumer only")
            await _run_account_creation(session_factory, publisher)
        elif consumer_name == "category-sync":
            logger.info("Running category-sync consumer only")
            await _run_category_sync(session_factory)
        else:
            logger.info("Running all consumers")
            await asyncio.gather(
                _run_user_sync(session_factory),
                _run_account_creation(session_factory, publisher),
                _run_category_sync(session_factory),
            )
    finally:
        await publisher.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RabbitMQ consumer worker")
    parser.add_argument(
        "--consumer",
        choices=["user-sync", "account-creation", "category-sync"],
        default=None,
        help="Run a specific consumer (default: all)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.consumer))
