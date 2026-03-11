from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IUnitOfWork


class SQLAlchemyUnitOfWork(IUnitOfWork):
    """Wraps an AsyncSession to control transaction boundaries.

    Repositories call ``flush()`` to push changes to the database within
    the current transaction.  The service layer calls ``commit()`` via
    this UoW to finalise the transaction.  On exception the context
    manager automatically rolls back.

    The same ``AsyncSession`` instance **must** be shared between the
    UoW and all repositories participating in the transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> SQLAlchemyUnitOfWork:
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
