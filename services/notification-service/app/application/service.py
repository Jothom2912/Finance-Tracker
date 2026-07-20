"""Application service: turn a trigger event into (at most) one notification.

Write path only. Reads (feed listing / mark-read) live in the API adapter,
which talks to the repository directly.

Idempotency is a deterministic ``source_key`` per logical event + the unique
constraint as backstop. A fast-path ``source_key_exists`` check avoids the
IntegrityError in the common redelivery case; the race case still raises
``IntegrityError``, which the consumer ACKs as a benign duplicate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from contracts.events.bank import BankSyncCompletedEvent
from contracts.events.budget import BudgetMonthClosedEvent
from contracts.events.goal import GoalUpdatedEvent

from app.application.ports.outbound import IAccountOwnerPort, IEmailPort, IUnitOfWork
from app.domain.entities import Notification, NotificationContent
from app.domain.exceptions import AccountNotFound
from app.domain.messages import (
    build_bank_sync_completed,
    build_budget_month_closed,
    build_goal_reached,
)

logger = logging.getLogger(__name__)

# goal-service's GoalStatus.COMPLETED value — kept as a local literal rather
# than importing across the service boundary.
GOAL_STATUS_COMPLETED = "completed"


@dataclass(frozen=True)
class HandleResult:
    status: str  # created | duplicate | ignored_not_completed | account_not_found
    source_key: str | None = None
    notification_id: UUID | None = None


class NotificationService:
    def __init__(
        self,
        uow: IUnitOfWork,
        email: IEmailPort,
        account_owner: IAccountOwnerPort,
    ) -> None:
        self._uow = uow
        self._email = email
        self._account_owner = account_owner

    async def handle_bank_sync_completed(self, event: BankSyncCompletedEvent) -> HandleResult:
        content = build_bank_sync_completed(new_imported=event.new_imported, errors=event.errors)
        # correlation_id makes the key redelivery-stable while still letting a
        # genuinely new sync of the same connection notify again.
        source_key = f"bank.sync.completed:{event.connection_id}:{event.correlation_id}"
        return await self._create(user_id=event.user_id, content=content, source_key=source_key)

    async def handle_goal_updated(self, event: GoalUpdatedEvent) -> HandleResult:
        if event.status != GOAL_STATUS_COMPLETED:
            return HandleResult(status="ignored_not_completed")
        content = build_goal_reached(goal_name=event.name, target_amount=Decimal(event.target_amount))
        # once per goal, ever
        source_key = f"goal.reached:{event.goal_id}"
        return await self._create(user_id=event.user_id, content=content, source_key=source_key)

    async def handle_budget_month_closed(self, event: BudgetMonthClosedEvent) -> HandleResult:
        content = build_budget_month_closed(
            year=event.year, month=event.month, surplus_amount=Decimal(event.surplus_amount)
        )
        try:
            user_id = await self._account_owner.get_owner_user_id(event.account_id)
        except AccountNotFound:
            # The owning account is gone — nobody to notify. Drop (ACK).
            # AccountOwnerUnavailable is NOT caught here: it propagates so the
            # consumer retries/DLQs instead of silently losing the notification.
            logger.warning("month_closed: account %s not found — dropping", event.account_id)
            return HandleResult(status="account_not_found", source_key=event.source_key)
        return await self._create(user_id=user_id, content=content, source_key=event.source_key)

    async def _create(self, *, user_id: int, content: NotificationContent, source_key: str) -> HandleResult:
        if await self._uow.notifications.source_key_exists(source_key):
            return HandleResult(status="duplicate", source_key=source_key)

        notification = Notification.from_content(user_id=user_id, content=content, source_key=source_key)
        async with self._uow:
            # A concurrent insert (race with the exists-check above) raises
            # IntegrityError here — it propagates to the consumer, which ACKs.
            saved = await self._uow.notifications.add(notification)
            await self._uow.commit()

        await self._send_email_best_effort(user_id=user_id, content=content)
        return HandleResult(status="created", source_key=source_key, notification_id=saved.id)

    async def _send_email_best_effort(self, *, user_id: int, content: NotificationContent) -> None:
        # The notification is already persisted (the source of truth for the
        # feed); email is secondary, so a failure must not fail the message.
        try:
            await self._email.send(user_id=user_id, title=content.title, body=content.body)
        except Exception:  # noqa: BLE001 - best-effort side channel
            logger.warning("email send failed for user=%s (ignored)", user_id, exc_info=True)
