"""Projection consumer that materialises transaction events into MySQL.

Listens on ``transaction.*`` and upserts rows in the monolith MySQL
``Transaction`` table so legacy contexts (analytics, budget, GraphQL)
can keep reading from their local database while the microservice
owns the write path.

Follows the same pattern as :class:`CategorySyncConsumer`:
- UPSERT semantics (idempotent on re-delivery)
- Silently skips unknown event types with a warning
- Commits the MySQL session per event; re-raises to let BaseConsumer
  apply retry + DLQ
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from contracts.events.transaction import (
    TransactionCreatedEvent,
    TransactionDeletedEvent,
    TransactionUpdatedEvent,
)

from backend.consumers.base import BaseConsumer
from backend.models.mysql.transaction import Transaction as TransactionModel

logger = logging.getLogger(__name__)

_HANDLERS = {
    "transaction.created": "_sync_created",
    "transaction.updated": "_sync_updated",
    "transaction.deleted": "_sync_deleted",
}


class TransactionSyncConsumer(BaseConsumer):
    """Materialise transaction events from transaction-service into
    monolith MySQL as a read model.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        db_session_factory: object,
    ) -> None:
        super().__init__(
            rabbitmq_url=rabbitmq_url,
            queue_name="monolith.transaction_sync",
            routing_key="transaction.*",
            db_session_factory=db_session_factory,
        )
        self._session_factory = db_session_factory

    async def handle(self, event_data: dict[str, object]) -> None:
        event_type = str(event_data.get("event_type", ""))
        handler_name = _HANDLERS.get(event_type)
        if handler_name is None:
            logger.warning("Unknown transaction event type: %s", event_type)
            return

        handler = getattr(self, handler_name)
        await asyncio.to_thread(handler, event_data)

    # ── handlers ────────────────────────────────────────────────────

    def _sync_created(self, event_data: dict[str, object]) -> None:
        event = TransactionCreatedEvent.model_validate(event_data)
        session = self._session_factory()
        try:
            existing = (
                session.query(TransactionModel).filter(TransactionModel.idTransaction == event.transaction_id).first()
            )
            if existing is not None:
                logger.info(
                    "Transaction %d already exists, treating as replay",
                    event.transaction_id,
                )
                self._apply_fields(existing, event)
            else:
                session.add(self._build_model(event))

            session.commit()
            logger.info(
                "Synced transaction.created: id=%d amount=%s type=%s",
                event.transaction_id,
                event.amount,
                event.transaction_type,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _sync_updated(self, event_data: dict[str, object]) -> None:
        event = TransactionUpdatedEvent.model_validate(event_data)
        session = self._session_factory()
        try:
            model = (
                session.query(TransactionModel).filter(TransactionModel.idTransaction == event.transaction_id).first()
            )
            if model is None:
                logger.warning(
                    "Transaction %d not found for update, upserting from event",
                    event.transaction_id,
                )
                session.add(self._build_model(event))
            else:
                self._apply_fields(model, event)

            session.commit()
            logger.info(
                "Synced transaction.updated: id=%d amount=%s",
                event.transaction_id,
                event.amount,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _sync_deleted(self, event_data: dict[str, object]) -> None:
        event = TransactionDeletedEvent.model_validate(event_data)
        session = self._session_factory()
        try:
            model = (
                session.query(TransactionModel).filter(TransactionModel.idTransaction == event.transaction_id).first()
            )
            if model is None:
                logger.info(
                    "Transaction %d already absent, skipping delete",
                    event.transaction_id,
                )
                return

            session.delete(model)
            session.commit()
            logger.info("Synced transaction.deleted: id=%d", event.transaction_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ── mapping helpers ─────────────────────────────────────────────

    @staticmethod
    def _build_model(
        event: TransactionCreatedEvent | TransactionUpdatedEvent,
    ) -> TransactionModel:
        return TransactionModel(
            idTransaction=event.transaction_id,
            amount=_to_decimal(event.amount),
            description=event.description or None,
            date=_to_datetime(event.tx_date),
            type=event.transaction_type,
            Category_idCategory=event.category_id,
            Account_idAccount=event.account_id,
            created_at=datetime.utcnow(),
            subcategory_id=event.subcategory_id,
            categorization_tier=event.categorization_tier,
            categorization_confidence=event.categorization_confidence,
        )

    @staticmethod
    def _apply_fields(
        model: TransactionModel,
        event: TransactionCreatedEvent | TransactionUpdatedEvent,
    ) -> None:
        model.amount = _to_decimal(event.amount)
        model.description = event.description or None
        model.date = _to_datetime(event.tx_date)
        model.type = event.transaction_type
        model.Category_idCategory = event.category_id
        model.Account_idAccount = event.account_id
        model.subcategory_id = event.subcategory_id
        model.categorization_tier = event.categorization_tier
        model.categorization_confidence = event.categorization_confidence


def _to_decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid amount in event payload: {raw!r}") from exc


def _to_datetime(tx_date: date) -> datetime:
    if isinstance(tx_date, datetime):
        return tx_date
    return datetime.combine(tx_date, datetime.min.time())
