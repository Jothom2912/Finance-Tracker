from __future__ import annotations

from types import TracebackType
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
        # P2-32: IOutboxRepository is an ABC declaring app.domain.entities.OutboxEntry,
        # while shared's OutboxRepository returns messaging.outbox.OutboxEntry — two
        # frozen dataclasses with the same 10 fields and the same name, and no
        # inheritance relationship to satisfy a nominal ABC. Not a live bug (the
        # publisher reads attributes), and banking is one of the seven services the
        # finding names. The ignore goes when P2-32 turns the port into a Protocol.
        self.outbox = OutboxRepository(session, OutboxEventModel)  # type: ignore[assignment]  # P2-32

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type:
            await self.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
