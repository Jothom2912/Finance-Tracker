from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.postgres_category_repository import PostgresCategoryRepository
from app.adapters.outbound.postgres_outbox_repository import PostgresOutboxRepository
from app.adapters.outbound.postgres_result_repository import PostgresCategorizationResultRepository
from app.adapters.outbound.postgres_rule_repository import PostgresRuleRepository
from app.adapters.outbound.postgres_subcategory_repository import PostgresSubCategoryRepository
from app.application.ports.outbound import IUnitOfWork


class SQLAlchemyUnitOfWork(IUnitOfWork):
    """Wraps an AsyncSession and exposes all repositories.

    Repositories share the same session so flush/commit operate
    on one database transaction (outbox pattern guarantee).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.categories = PostgresCategoryRepository(session)
        self.subcategories = PostgresSubCategoryRepository(session)
        self.merchants = None  # type: ignore[assignment]
        self.rules = PostgresRuleRepository(session)
        self.results = PostgresCategorizationResultRepository(session)
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
