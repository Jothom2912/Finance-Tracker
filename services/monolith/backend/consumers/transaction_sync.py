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
from backend.models.mysql.category import Category as CategoryModel
from backend.models.mysql.subcategory import SubCategory as SubCategoryModel
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
                self._apply_fields(session, existing, event)
            else:
                session.add(self._build_model(session, event))

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
                session.add(self._build_model(session, event))
            else:
                self._apply_fields(session, model, event)

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

    def _build_model(
        self,
        session: object,
        event: TransactionCreatedEvent | TransactionUpdatedEvent,
    ) -> TransactionModel:
        category_id, subcategory_id = self._resolve_category_fks(session, event)
        return TransactionModel(
            idTransaction=event.transaction_id,
            amount=_to_decimal(event.amount),
            description=event.description or None,
            date=_to_datetime(event.tx_date),
            type=event.transaction_type,
            Category_idCategory=category_id,
            Account_idAccount=event.account_id,
            created_at=datetime.utcnow(),
            subcategory_id=subcategory_id,
            categorization_tier=event.categorization_tier,
            categorization_confidence=event.categorization_confidence,
        )

    def _apply_fields(
        self,
        session: object,
        model: TransactionModel,
        event: TransactionCreatedEvent | TransactionUpdatedEvent,
    ) -> None:
        category_id, subcategory_id = self._resolve_category_fks(session, event)
        model.amount = _to_decimal(event.amount)
        model.description = event.description or None
        model.date = _to_datetime(event.tx_date)
        model.type = event.transaction_type
        model.Category_idCategory = category_id
        model.Account_idAccount = event.account_id
        model.subcategory_id = subcategory_id
        model.categorization_tier = event.categorization_tier
        model.categorization_confidence = event.categorization_confidence

    @staticmethod
    def _resolve_category_fks(
        session: object,
        event: TransactionCreatedEvent | TransactionUpdatedEvent,
    ) -> tuple[int | None, int | None]:
        """Only set category/subcategory FKs that exist in the MySQL read model.

        Categorization-service IDs are not replicated to monolith SubCategory
        yet, so blind FK assignment fails the whole projection insert.
        """
        category_id = event.category_id
        if category_id is not None:
            exists = (
                session.query(CategoryModel.idCategory)
                .filter(
                    CategoryModel.idCategory == category_id,
                )
                .first()
            )
            if exists is None:
                logger.warning(
                    "Category %d missing in MySQL projection for transaction %d — omitting FK",
                    category_id,
                    event.transaction_id,
                )
                category_id = None

        subcategory_id = event.subcategory_id
        if subcategory_id is not None:
            exists = (
                session.query(SubCategoryModel.id)
                .filter(
                    SubCategoryModel.id == subcategory_id,
                )
                .first()
            )
            if exists is None:
                logger.warning(
                    "SubCategory %d missing in MySQL projection for transaction %d — omitting FK",
                    subcategory_id,
                    event.transaction_id,
                )
                subcategory_id = None

        return category_id, subcategory_id


def _to_decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid amount in event payload: {raw!r}") from exc


def _to_datetime(tx_date: date) -> datetime:
    if isinstance(tx_date, datetime):
        return tx_date
    return datetime.combine(tx_date, datetime.min.time())
