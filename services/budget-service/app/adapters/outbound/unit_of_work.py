from __future__ import annotations

from typing import Self

from messaging import OutboxRepository
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_monthly_budget_repository import (
    PostgresMonthlyBudgetRepository,
)
from app.application.ports.outbound import IUnitOfWork
from app.models import OutboxEventModel


class SQLAlchemyUnitOfWork(IUnitOfWork):
    """Repos share one session — flush() in repos, commit() here.

    Structurally impossible to commit domain data without the outbox row.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.monthly_budgets = PostgresMonthlyBudgetRepository(session)
        self.outbox = OutboxRepository(session, OutboxEventModel)

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
