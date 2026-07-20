"""Consumer for the three F1 trigger events → in-app notifications.

One queue bound to all three routing keys (none has a slow/flaky dependency,
so no per-concern queue isolation is needed — cf. the embed-worker decision).
Connection/topology/retry/DLQ boilerplate lives in ``messaging.ConsumerBase``.

Idempotency: the service writes a deterministic ``source_key`` guarded by a
unique constraint. A duplicate (redelivery, or a race past the fast-path
check) raises ``IntegrityError``, which we treat as a benign duplicate and
ACK — mirroring goal-service's budget_month_closed_consumer.

Run as a standalone process::

    python -m app.workers.notification_consumer
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_pika.abc import AbstractIncomingMessage
from contracts.events.bank import BankSyncCompletedEvent
from contracts.events.budget import BudgetMonthClosedEvent
from contracts.events.goal import GoalUpdatedEvent
from messaging import ConsumerBase, PoisonMessageError, setup_worker_logging
from sqlalchemy.exc import IntegrityError

from app.adapters.outbound.account_adapter import AccountServiceAdapter
from app.adapters.outbound.log_email_adapter import LogEmailAdapter
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.service import HandleResult, NotificationService
from app.config import settings
from app.database import async_session_factory

logger = logging.getLogger(__name__)

QUEUE_NAME = "notification_service.events"
ROUTING_KEYS = ("bank.sync.completed", "goal.updated", "budget.month_closed")


class NotificationConsumer(ConsumerBase):
    def __init__(self) -> None:
        super().__init__(
            rabbitmq_url=settings.RABBITMQ_URL,
            queue_name=QUEUE_NAME,
            routing_keys=ROUTING_KEYS,
        )
        # Stateless collaborators shared across messages.
        self._email = LogEmailAdapter()
        self._account_owner = AccountServiceAdapter(
            base_url=settings.ACCOUNT_SERVICE_URL,
            api_key=settings.INTERNAL_API_KEY,
            timeout=settings.ACCOUNT_SERVICE_TIMEOUT,
        )

    async def handle(self, payload: dict[str, Any], message: AbstractIncomingMessage) -> None:
        event_type = payload.get("event_type")
        correlation_id = payload.get("correlation_id", "unknown")

        try:
            async with async_session_factory() as session:
                service = NotificationService(SQLAlchemyUnitOfWork(session), self._email, self._account_owner)
                result = await self._dispatch(service, event_type, payload, correlation_id)
        except IntegrityError:
            logger.info(
                "duplicate source_key (event_type=%s correlation_id=%s) — benign race, acking",
                event_type,
                correlation_id,
            )
            return

        logger.info(
            "handled %s: status=%s source_key=%s correlation_id=%s",
            event_type,
            result.status,
            result.source_key,
            correlation_id,
        )

    async def _dispatch(
        self,
        service: NotificationService,
        event_type: str | None,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> HandleResult:
        if event_type == "bank.sync.completed":
            return await service.handle_bank_sync_completed(
                self._parse(BankSyncCompletedEvent, payload, correlation_id)
            )
        if event_type == "goal.updated":
            return await service.handle_goal_updated(self._parse(GoalUpdatedEvent, payload, correlation_id))
        if event_type == "budget.month_closed":
            return await service.handle_budget_month_closed(
                self._parse(BudgetMonthClosedEvent, payload, correlation_id)
            )
        # The queue is only bound to the three keys above, so anything else is
        # a routing/config bug, not a transient failure — send it to the DLQ.
        raise PoisonMessageError(f"unexpected event_type {event_type!r}")

    @staticmethod
    def _parse(model: type[Any], payload: dict[str, Any], correlation_id: str) -> Any:
        try:
            return model.model_validate(payload)
        except Exception as err:  # noqa: BLE001 - normalize to poison
            raise PoisonMessageError(f"invalid {model.__name__} payload (correlation_id={correlation_id})") from err


async def main() -> None:
    setup_worker_logging(__name__)
    await NotificationConsumer().run()


if __name__ == "__main__":
    asyncio.run(main())
