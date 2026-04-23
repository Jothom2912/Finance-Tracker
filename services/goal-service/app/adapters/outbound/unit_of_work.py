from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_goal_repository import AsyncPostgresGoalRepository
from app.adapters.outbound.postgres_outbox_repository import PostgresOutboxRepository
from app.application.ports.outbound import IUnitOfWork


class SQLAlchemyUnitOfWork(IUnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.goals = AsyncPostgresGoalRepository(session)
        self.outbox = PostgresOutboxRepository(session)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type:
            await self.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
