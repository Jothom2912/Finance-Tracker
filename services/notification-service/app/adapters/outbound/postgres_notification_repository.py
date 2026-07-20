from __future__ import annotations

from uuid import UUID

from messaging import utcnow
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import INotificationRepository
from app.domain.entities import Notification, NotificationType
from app.models import NotificationModel


def _to_entity(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        user_id=model.user_id,
        type=NotificationType(model.type),
        title=model.title,
        body=model.body,
        source_key=model.source_key,
        created_at=model.created_at,
        read_at=model.read_at,
        dismissed_at=model.dismissed_at,
    )


class PostgresNotificationRepository(INotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Notification:
        model = NotificationModel(
            user_id=notification.user_id,
            type=notification.type.value,
            title=notification.title,
            body=notification.body,
            source_key=notification.source_key,
        )
        self._session.add(model)
        # Flush issues the INSERT so a duplicate source_key surfaces its
        # IntegrityError here (caller ACKs it as a benign duplicate).
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def source_key_exists(self, source_key: str) -> bool:
        result = await self._session.execute(
            select(NotificationModel.id).where(NotificationModel.source_key == source_key).limit(1)
        )
        return result.first() is not None

    async def list_for_user(
        self, user_id: int, *, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        stmt = (
            select(NotificationModel)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.dismissed_at.is_(None),
            )
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if unread_only:
            stmt = stmt.where(NotificationModel.read_at.is_(None))
        result = await self._session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def unread_count(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(NotificationModel)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.read_at.is_(None),
                NotificationModel.dismissed_at.is_(None),
            )
        )
        return int(result.scalar_one())

    async def mark_read(self, notification_id: UUID, user_id: int) -> bool:
        # coalesce keeps the first read time and makes a re-mark idempotent
        # while rowcount still reflects ownership (for 404 semantics).
        result = await self._session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
            .values(read_at=func.coalesce(NotificationModel.read_at, utcnow()))
        )
        return result.rowcount > 0

    async def mark_all_read(self, user_id: int) -> int:
        result = await self._session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.read_at.is_(None),
                NotificationModel.dismissed_at.is_(None),
            )
            .values(read_at=utcnow())
        )
        return int(result.rowcount)

    async def dismiss(self, notification_id: UUID, user_id: int) -> bool:
        result = await self._session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
            .values(dismissed_at=func.coalesce(NotificationModel.dismissed_at, utcnow()))
        )
        return result.rowcount > 0
