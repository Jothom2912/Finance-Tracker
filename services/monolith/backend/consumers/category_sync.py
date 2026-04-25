from __future__ import annotations

import asyncio
import logging

from contracts.events.category import (
    CategoryCreatedEvent,
    CategoryDeletedEvent,
    CategoryUpdatedEvent,
)
from sqlalchemy import func

from backend.consumers.base import BaseConsumer
from backend.models.mysql.category import Category as CategoryModel

logger = logging.getLogger(__name__)

_HANDLERS = {
    "category.created": "_sync_created",
    "category.updated": "_sync_updated",
    "category.deleted": "_sync_deleted",
}


class CategorySyncConsumer(BaseConsumer):
    """Syncs category data from transaction-service into the monolith
    MySQL Category table so Budget/MonthlyBudget services can continue
    reading categories locally.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        db_session_factory: object,
    ) -> None:
        super().__init__(
            rabbitmq_url=rabbitmq_url,
            queue_name="monolith.category_sync",
            routing_key="category.*",
            db_session_factory=db_session_factory,
        )
        self._session_factory = db_session_factory

    async def handle(self, event_data: dict[str, object]) -> None:
        event_type = str(event_data.get("event_type", ""))
        handler_name = _HANDLERS.get(event_type)
        if handler_name is None:
            logger.warning("Unknown category event type: %s", event_type)
            return

        handler = getattr(self, handler_name)
        await asyncio.to_thread(handler, event_data)

    def _sync_created(self, event_data: dict[str, object]) -> None:
        event = CategoryCreatedEvent.model_validate(event_data)
        session = self._session_factory()
        try:
            existing = session.query(CategoryModel).filter(CategoryModel.idCategory == event.category_id).first()
            if existing:
                logger.info(
                    "Category %d already exists, skipping create",
                    event.category_id,
                )
                return

            # Append after the highest existing display_order so new
            # categories land at the end of the UI list rather than at 0.
            # Single-writer in practice: CategorySyncConsumer is the only
            # writer to this table, enforced by test_read_only_projections.
            # The COALESCE+MAX is one statement but not INSERT...SELECT,
            # so a theoretical race exists if two category.created events
            # process concurrently — acceptable given the single-consumer
            # topology.
            max_order = (
                session.query(
                    func.coalesce(func.max(CategoryModel.display_order), 0)
                ).scalar()
            )

            model = CategoryModel(
                idCategory=event.category_id,
                name=event.name,
                type=event.category_type,
                display_order=max_order + 1,
            )
            session.add(model)
            session.commit()
            logger.info("Synced category.created: id=%d name=%s", event.category_id, event.name)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _sync_updated(self, event_data: dict[str, object]) -> None:
        event = CategoryUpdatedEvent.model_validate(event_data)
        session = self._session_factory()
        try:
            model = session.query(CategoryModel).filter(CategoryModel.idCategory == event.category_id).first()
            if model is None:
                logger.warning(
                    "Category %d not found for update, creating it",
                    event.category_id,
                )
                model = CategoryModel(
                    idCategory=event.category_id,
                    name=event.name,
                    type=event.category_type,
                )
                session.add(model)
            else:
                model.name = event.name
                model.type = event.category_type

            session.commit()
            logger.info("Synced category.updated: id=%d name=%s", event.category_id, event.name)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _sync_deleted(self, event_data: dict[str, object]) -> None:
        event = CategoryDeletedEvent.model_validate(event_data)
        session = self._session_factory()
        try:
            model = session.query(CategoryModel).filter(CategoryModel.idCategory == event.category_id).first()
            if model is None:
                logger.info(
                    "Category %d already absent, skipping delete",
                    event.category_id,
                )
                return

            session.delete(model)
            session.commit()
            logger.info("Synced category.deleted: id=%d name=%s", event.category_id, event.name)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
