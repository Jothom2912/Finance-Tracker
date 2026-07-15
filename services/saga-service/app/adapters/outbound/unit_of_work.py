from __future__ import annotations

from messaging import OutboxRepository
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_saga_repository import PostgresSagaRepository
from app.application.ports.outbound import IUnitOfWork
from app.models import OutboxEventModel


class SQLAlchemyUnitOfWork(IUnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.sagas = PostgresSagaRepository(session)
        self.outbox = OutboxRepository(session, OutboxEventModel)

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        if exc_type is not None:
            await self._session.rollback()

    async def commit(self) -> None:
        await self._session.commit()
