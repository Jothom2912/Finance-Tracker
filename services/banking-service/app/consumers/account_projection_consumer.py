"""Consumer that keeps accounts_projection in sync with account-service events.

Listens on account.created and account.updated, upserts into accounts_projection.
This projection is used by start_sync_saga for account_name enrichment.

Normalizes the field name inconsistency between events:
  - AccountCreatedEvent has ``account_name``
  - AccountUpdatedEvent has ``name``

Connection/topology/retry/DLQ boilerplate lives in the shared
``messaging.ConsumerBase``.  Deduplication deliberately does NOT use the
base's ``InboxDeduplicator`` hook: the processed_events row must commit
atomically with the projection upsert, so it is written inside ``handle``'s
own DB transaction (IntegrityError on commit = benign concurrent duplicate).

Run as a standalone process::

    python -m app.consumers.account_projection_consumer
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_pika.abc import AbstractIncomingMessage
from messaging import ConsumerBase, setup_worker_logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_account_projection_repository import (
    PostgresAccountProjectionRepository,
)
from app.config import settings
from app.database import async_session_factory
from app.models.processed_events import ProcessedEventModel

logger = logging.getLogger(__name__)

QUEUE_NAME = "banking.account_sync"
ROUTING_KEYS = ["account.created", "account.updated"]


class AccountProjectionConsumer(ConsumerBase):
    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEYS,
        )

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        correlation_id = payload.get("correlation_id", "")

        async with async_session_factory() as session:
            if correlation_id and await self._is_duplicate(session, correlation_id):
                logger.info("Skipping duplicate (correlation_id=%s)", correlation_id)
                return

            account_id = payload["account_id"]
            user_id = payload["user_id"]
            account_name = payload.get("account_name") or payload.get("name", "Unknown")

            repo = PostgresAccountProjectionRepository(session)
            await repo.upsert(account_id, user_id, account_name)

            if correlation_id:
                session.add(
                    ProcessedEventModel(
                        correlation_id=correlation_id,
                        consumer_name=QUEUE_NAME,
                    )
                )

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.info(
                    "Duplicate on commit (correlation_id=%s) — benign race",
                    correlation_id,
                )
                return

        logger.info(
            "Upserted account projection: account_id=%d, name=%s",
            account_id,
            account_name,
        )

    @staticmethod
    async def _is_duplicate(session: AsyncSession, correlation_id: str) -> bool:
        result = await session.execute(
            select(ProcessedEventModel).where(
                ProcessedEventModel.correlation_id == correlation_id,
                ProcessedEventModel.consumer_name == QUEUE_NAME,
            )
        )
        return result.scalar_one_or_none() is not None


async def main() -> None:
    setup_worker_logging(__name__)
    await AccountProjectionConsumer().run()


if __name__ == "__main__":
    asyncio.run(main())
