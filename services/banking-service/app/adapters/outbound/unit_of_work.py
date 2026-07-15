from __future__ import annotations

from typing import Self

from messaging import OutboxRepository
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_account_projection_repository import (
    PostgresAccountProjectionRepository,
)
from app.adapters.outbound.postgres_bank_connection_repository import (
    PostgresBankConnectionRepository,
)
from app.adapters.outbound.postgres_pending_auth_repository import (
    PostgresPendingAuthRepository,
)
from app.application.ports.outbound import IUnitOfWork
from app.models.outbox import OutboxEventModel


class SQLAlchemyUnitOfWork(IUnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.connections = PostgresBankConnectionRepository(session)
        self.pending_auth = PostgresPendingAuthRepository(session)
        self.accounts = PostgresAccountProjectionRepository(session)
        self.outbox = OutboxRepository(session, OutboxEventModel)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
