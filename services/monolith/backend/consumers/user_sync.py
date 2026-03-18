from __future__ import annotations

import asyncio
import logging

from contracts.events.user import UserCreatedEvent

from backend.consumers.base import BaseConsumer
from backend.models.mysql.user import User as UserModel

logger = logging.getLogger(__name__)


class UserSyncConsumer(BaseConsumer):
    """Syncs user data from user-service into the monolith MySQL User table.

    Listens on ``user.created`` and inserts a local copy of the user.
    The MySQL User table is a read-cache — user-service PostgreSQL is
    source of truth.  No FK constraints reference this table, so the
    sync can run independently of other consumers.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        db_session_factory: object,
    ) -> None:
        super().__init__(
            rabbitmq_url=rabbitmq_url,
            queue_name="monolith.user_sync",
            routing_key="user.created",
        )
        self._session_factory = db_session_factory

    async def handle(self, event_data: dict[str, object]) -> None:
        event = UserCreatedEvent.model_validate(event_data)
        logger.info(
            "Syncing user_id=%d to MySQL (correlation_id=%s)",
            event.user_id,
            event.correlation_id,
        )
        await asyncio.to_thread(self._sync_user, event)

    def _sync_user(self, event: UserCreatedEvent) -> None:
        """Synchronous DB work — called via ``asyncio.to_thread``."""
        session = self._session_factory()
        try:
            existing = session.query(UserModel).filter(UserModel.idUser == event.user_id).first()
            if existing:
                logger.info(
                    "User %d already exists in MySQL — skipping",
                    event.user_id,
                )
                return

            model = UserModel(
                idUser=event.user_id,
                username=event.username,
                email=event.email,
                password="synced-from-user-service",
            )
            session.add(model)
            session.commit()
            logger.info("User %d synced to MySQL", event.user_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
