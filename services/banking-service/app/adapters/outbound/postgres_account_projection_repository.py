from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts_projection import AccountsProjectionModel


class PostgresAccountProjectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_account_name(self, account_id: int) -> Optional[str]:
        result = await self._session.execute(
            select(AccountsProjectionModel.account_name).where(
                AccountsProjectionModel.account_id == account_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self, account_id: int, user_id: int, account_name: str
    ) -> None:
        stmt = (
            pg_insert(AccountsProjectionModel)
            .values(
                account_id=account_id,
                user_id=user_id,
                account_name=account_name,
            )
            .on_conflict_do_update(
                index_elements=["account_id"],
                set_={"user_id": user_id, "account_name": account_name},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
