from __future__ import annotations

import asyncio
import logging

from contracts.events.account import (
    AccountCreatedEvent,
    AccountCreationFailedEvent,
)
from contracts.events.user import UserCreatedEvent

from backend.account.adapters.outbound.mysql_account_repository import (
    MySQLAccountRepository,
)
from backend.account.domain.entities import Account
from backend.consumers.base import BaseConsumer

logger = logging.getLogger(__name__)


class IEventPublisher:
    """Minimal publisher interface for saga events."""

    async def publish(self, event: object) -> None: ...


class AccountCreationConsumer(BaseConsumer):
    """Creates a default account when a new user is registered.

    Listens on ``user.created`` with its own queue — independent of
    UserSyncConsumer.  No FK to User table, so this consumer does not
    need the user to exist in MySQL first.

    On success publishes ``AccountCreatedEvent`` (saga happy path).
    On failure publishes ``AccountCreationFailedEvent`` (saga compensation)
    and re-raises so the base consumer can apply retry logic.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        db_session_factory: object,
        publisher: IEventPublisher,
    ) -> None:
        super().__init__(
            rabbitmq_url=rabbitmq_url,
            queue_name="monolith.account_creation",
            routing_key="user.created",
        )
        self._session_factory = db_session_factory
        self._publisher = publisher

    async def handle(self, event_data: dict[str, object]) -> None:
        event = UserCreatedEvent.model_validate(event_data)
        logger.info(
            "Creating default account for user_id=%d (correlation_id=%s)",
            event.user_id,
            event.correlation_id,
        )

        try:
            account = await asyncio.to_thread(
                self._create_default_account, event.user_id
            )

            await self._publisher.publish(
                AccountCreatedEvent(
                    account_id=account.id,
                    user_id=event.user_id,
                    account_name=account.name,
                    correlation_id=event.correlation_id,
                )
            )
            logger.info(
                "Default account %d created for user %d",
                account.id,
                event.user_id,
            )

        except Exception as exc:
            await self._publisher.publish(
                AccountCreationFailedEvent(
                    user_id=event.user_id,
                    reason=str(exc),
                    correlation_id=event.correlation_id,
                )
            )
            raise

    def _create_default_account(self, user_id: int) -> Account:
        """Synchronous DB work — called via ``asyncio.to_thread``."""
        session = self._session_factory()
        try:
            repo = MySQLAccountRepository(session)
            account = repo.create(
                Account(id=None, name="Default Account", saldo=0.0, user_id=user_id)
            )
            return account
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
