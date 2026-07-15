"""Consumer that creates a default account when a new user registers.

Listens on ``user.created`` events from finans_tracker.events topic exchange.
Replaces the legacy monolith account-creation-consumer.

Idempotency:
- Fast-path: skips if user already has accounts in Postgres
- DB-level: partial unique index ``one_default_per_user`` prevents duplicates
- UniqueViolation caught and logged (race condition between re-deliveries)

Reliability: connection/topology/retry/DLQ boilerplate lives in the shared
``messaging.ConsumerBase`` — whose retry mechanics (republish to our OWN
queue via the default exchange with an incremented ``x-retry-count``
header) were modelled on this very consumer. Unparseable payloads raise
``PoisonMessageError`` and are dead-lettered without retries.

DB access is sync SQLAlchemy (this service's persistence is still sync,
see P3-01) and runs via ``asyncio.to_thread`` so it never blocks the
consumer's event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from aio_pika.abc import AbstractIncomingMessage
from messaging import ConsumerBase, PoisonMessageError, setup_worker_logging
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

QUEUE_NAME = "account_service.account_creation"
ROUTING_KEY = "user.created"
MAX_RETRIES = 3


class AccountCreationConsumer(ConsumerBase):
    """Creates default accounts for newly registered users."""

    def __init__(self, rabbitmq_url: str, session_factory: sessionmaker) -> None:
        super().__init__(
            rabbitmq_url=rabbitmq_url,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEY,
            max_retries=MAX_RETRIES,
        )
        self._session_factory = session_factory

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        try:
            user_id = int(payload["user_id"])
        except Exception as err:
            raise PoisonMessageError("Invalid user.created payload") from err
        correlation_id = payload.get("correlation_id")

        logger.info(
            "Received user.created for user_id=%d (correlation_id=%s)",
            user_id,
            correlation_id,
        )
        await asyncio.to_thread(self._handle_user_created, user_id)

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


async def main() -> None:
    setup_worker_logging(__name__)
    consumer = AccountCreationConsumer(RABBITMQ_URL, build_session_factory())
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
