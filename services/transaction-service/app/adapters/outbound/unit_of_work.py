from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_category_repository import (
    PostgresCategoryRepository,
)
from app.adapters.outbound.postgres_outbox_repository import (
    PostgresOutboxRepository,
)
from app.adapters.outbound.postgres_planned_repository import (
    PostgresPlannedTransactionRepository,
)
from app.adapters.outbound.postgres_transaction_repository import (
    PostgresTransactionRepository,
)
from app.application.ports.outbound import IUnitOfWork


class SQLAlchemyUnitOfWork(IUnitOfWork):
    """Wraps an AsyncSession and exposes all repositories.

    Repositories are created with the **same** session instance so
    ``flush()`` in any repository and ``commit()`` here all operate
    on one database transaction.  This makes it structurally impossible
    to commit domain data without the outbox row (or vice-versa).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.transactions = PostgresTransactionRepository(session)
        self.planned = PostgresPlannedTransactionRepository(session)
        self.categories = PostgresCategoryRepository(session)
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
