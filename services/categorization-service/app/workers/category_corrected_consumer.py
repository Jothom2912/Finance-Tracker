"""Consumer for transaction.category_corrected events (F1-03 feedback loop).

When a user manually corrects a transaction's category, transaction-
service emits ``transaction.category_corrected``.  This consumer turns
the correction into a LEARNED rule: an auto-managed, user-scoped
``pattern_type=MERCHANT`` rule at priority 10 (the top of the ladder —
learned 10 < user-created 50 < seeds 100), keyed on the normalized
description.  The next import of the same merchant auto-categorizes
correctly via the ordinary rule engine — one matching mechanism, and
the learned rule is visible/deletable in the rules UI.

Upsert semantics: one learned rule per (user, normalized pattern) —
re-corrections retarget the existing row (last correction wins) and
reactivate it if the user had deactivated it.  The partial unique index
``uq_rules_user_pattern`` (migration 007) backstops concurrent
redeliveries.

Skipped as unlearnable (inbox row still written, message ACKed):
- empty/whitespace/digits-only descriptions (nothing to match on)
- corrections without a subcategory (parent-only edits — the rules
  schema targets subcategories; documented limitation)
- subcategory ids missing from the local taxonomy (stale read copy —
  learning from them would violate the FK and poison the retry loop)

Deduplication mirrors ``transaction_consumer``: the inbox row commits
atomically with the rule write; the UNIQUE constraint on
(message_id, consumer_name) turns duplicate-processing races into a
benign rollback+ACK.  Inbox cleanup runs in transaction_consumer only
(shared table, one janitor is enough).

Note on cache freshness: this worker runs in its own process, so it
cannot invalidate the API process's per-user engine overlay — learned
rules take effect within the provider TTL (≤60s) everywhere.

Run as a standalone process::

    python -m app.workers.category_corrected_consumer
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

from app.adapters.outbound.postgres_rule_repository import PostgresRuleRepository
from app.config import settings
from app.database import async_session_factory
from app.domain.entities import CategorizationRule
from app.domain.merchant_normalization import normalize_merchant_pattern
from app.domain.value_objects import PatternType
from app.models import ProcessedEventModel, SubCategoryModel

logger = logging.getLogger(__name__)

QUEUE_NAME = "categorization.category_corrected"
ROUTING_KEY = "transaction.category_corrected"
LEARNED_RULE_PRIORITY = 10


class CategoryCorrectedConsumer(ConsumerBase):
    """Turns manual category corrections into learned user rules."""

    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEY,
        )

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        message_id = payload.get("correlation_id", "")
        event_type = payload.get("event_type", "")

        async with async_session_factory() as session:
            if message_id and await self._is_duplicate(session, message_id):
                logger.info("Skipping duplicate (message_id=%s)", message_id)
                return

            await self._handle(session, payload)

            if message_id:
                self._add_inbox_row(session, message_id, event_type)

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                detail = str(exc).lower()
                if "processed_events" in detail or "uq_processed_events" in detail:
                    logger.info(
                        "Duplicate detected on commit (message_id=%s) — benign race, acking",
                        message_id,
                    )
                    return
                if "uq_rules_user_pattern" in detail:
                    # Two corrections for the same merchant raced; the
                    # first writer's rule stands, the next correction
                    # retargets it.  Redelivering would not converge
                    # differently, so ACK.
                    logger.info("Learned-rule upsert race — benign, acking")
                    return
                raise

    async def _handle(self, session: AsyncSession, event_data: dict) -> None:
        user_id = event_data.get("user_id")
        subcategory_id = event_data.get("subcategory_id")
        description = event_data.get("description", "")
        pattern = normalize_merchant_pattern(description or "")

        if not user_id or not pattern:
            logger.info(
                "Unlearnable correction (user_id=%s, empty pattern from '%.40s') — skipping",
                user_id,
                description,
            )
            return
        if not subcategory_id:
            logger.info("Parent-only correction for '%.40s' — no subcategory to learn, skipping", pattern)
            return

        known = await session.execute(select(SubCategoryModel.id).where(SubCategoryModel.id == subcategory_id))
        if known.scalar_one_or_none() is None:
            logger.warning(
                "Correction targets unknown subcategory %s (stale taxonomy copy?) — skipping",
                subcategory_id,
            )
            return

        repo = PostgresRuleRepository(session)
        existing = await repo.find_by_user_and_pattern(user_id, PatternType.MERCHANT, pattern)
        if existing is not None:
            await repo.update(
                existing.id,
                matches_subcategory_id=subcategory_id,
                active=True,
            )
            logger.info(
                "Learned rule retargeted: user=%s '%s' -> subcategory %s",
                user_id,
                pattern,
                subcategory_id,
            )
        else:
            await repo.create(
                CategorizationRule(
                    id=None,
                    user_id=user_id,
                    priority=LEARNED_RULE_PRIORITY,
                    pattern_type=PatternType.MERCHANT,
                    pattern_value=pattern,
                    matches_subcategory_id=subcategory_id,
                    active=True,
                ),
            )
            logger.info(
                "Learned rule created: user=%s '%s' -> subcategory %s",
                user_id,
                pattern,
                subcategory_id,
            )

    @staticmethod
    async def _is_duplicate(session: AsyncSession, message_id: str) -> bool:
        stmt = select(ProcessedEventModel).where(
            ProcessedEventModel.message_id == message_id,
            ProcessedEventModel.consumer_name == QUEUE_NAME,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _add_inbox_row(session: AsyncSession, message_id: str, event_type: str) -> None:
        """Add inbox row to the current session (committed by caller)."""
        session.add(
            ProcessedEventModel(
                message_id=message_id,
                consumer_name=QUEUE_NAME,
                event_type=event_type,
            ),
        )


async def main() -> None:
    setup_worker_logging(__name__)
    consumer = CategoryCorrectedConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
