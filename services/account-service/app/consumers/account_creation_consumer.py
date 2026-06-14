"""Consumer that creates a default account when a new user registers.

Listens on ``user.created`` events from finans_tracker.events topic exchange.
Replaces the legacy monolith account-creation-consumer.

Idempotency:
- Fast-path: skips if user already has accounts in Postgres
- DB-level: partial unique index ``one_default_per_user`` prevents duplicates
- UniqueViolation caught and logged (race condition between re-deliveries)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.outbound.outbox_repository import SyncOutboxRepository
from app.adapters.outbound.postgresql_account_group_repository import (
    PostgresAccountGroupRepository,
)
from app.adapters.outbound.postgresql_account_repository import (
    PostgresAccountRepository,
)
from app.adapters.outbound.user_adapter import UserServiceAdapter
from app.application.dto import AccountCreate
from app.application.service import AccountService

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

EXCHANGE_NAME = "finans_tracker.events"
QUEUE_NAME = "account_service.account_creation"
ROUTING_KEY = "user.created"


class AccountCreationConsumer:
    """Creates default accounts for newly registered users."""

    def __init__(self, rabbitmq_url: str, session_factory: sessionmaker) -> None:
        self._rabbitmq_url = rabbitmq_url
        self._session_factory = session_factory

    async def run(self) -> None:
        connection = await aio_pika.connect_robust(self._rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)

        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
        )

        queue = await channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=ROUTING_KEY)

        logger.info(
            "Connected — queue=%s, routing_key=%s, exchange=%s",
            QUEUE_NAME,
            ROUTING_KEY,
            EXCHANGE_NAME,
        )

        await queue.consume(self._on_message)

        try:
            await asyncio.Future()
        finally:
            await connection.close()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process():
            try:
                body = json.loads(message.body.decode("utf-8"))
                user_id = int(body["user_id"])
                correlation_id = body.get("correlation_id")

                logger.info(
                    "Received user.created for user_id=%d (correlation_id=%s)",
                    user_id,
                    correlation_id,
                )

                await asyncio.to_thread(self._handle_user_created, user_id)

            except Exception:
                logger.exception("Failed to handle user.created event")
                raise

    def _handle_user_created(self, user_id: int) -> None:
        session = self._session_factory()
        try:
            account_repo = PostgresAccountRepository(session)

            # Fast-path: skip if user already has accounts
            existing = account_repo.get_all(user_id)
            if existing:
                logger.info(
                    "User %d already has %d account(s), skipping default creation",
                    user_id,
                    len(existing),
                )
                return

            outbox = SyncOutboxRepository(session)
            service = AccountService(
                account_repository=account_repo,
                account_group_repository=PostgresAccountGroupRepository(session),
                user_port=UserServiceAdapter(),
                outbox=outbox,
                commit_fn=session.commit,
            )

            try:
                account = service.create_account(
                    AccountCreate(
                        name="Default Account",
                        saldo=0.0,
                        budget_start_day=1,
                        User_idUser=user_id,
                    )
                )
                logger.info(
                    "Default account %d created for user %d",
                    account.idAccount,
                    user_id,
                )
            except Exception as exc:
                if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                    session.rollback()
                    logger.info(
                        "Default account already exists for user %d (unique constraint), skipping",
                        user_id,
                    )
                else:
                    raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def build_session_factory() -> sessionmaker:
    """Create a sync SessionLocal factory."""
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
