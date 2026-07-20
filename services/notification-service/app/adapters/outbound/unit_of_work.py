from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_notification_repository import (
    PostgresNotificationRepository,
)
from app.application.ports.outbound import IUnitOfWork


class SQLAlchemyUnitOfWork(IUnitOfWork):
    """Terminal consumer + read API — one repository, no outbox (the service
    emits no events of its own)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.notifications = PostgresNotificationRepository(session)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
