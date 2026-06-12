from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import BankConnection
from app.models.bank_connection import BankConnectionModel


class PostgresBankConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, connection: BankConnection) -> BankConnection:
        row = BankConnectionModel(
            id=connection.id,
            account_id=connection.account_id,
            user_id=connection.user_id,
            session_id=connection.session_id,
            bank_name=connection.bank_name,
            bank_country=connection.bank_country,
            bank_account_uid=connection.bank_account_uid,
            bank_account_iban=connection.bank_account_iban,
            status=connection.status,
            expires_at=connection.expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        connection.created_at = row.created_at
        return connection

    async def commit(self) -> None:
        await self._session.commit()

    async def get_by_id(self, connection_id: UUID) -> Optional[BankConnection]:
        result = await self._session.execute(
            select(BankConnectionModel).where(BankConnectionModel.id == str(connection_id))
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_active_by_uid(
        self, bank_account_uid: str, account_id: int,
    ) -> Optional[BankConnection]:
        result = await self._session.execute(
            select(BankConnectionModel).where(
                BankConnectionModel.bank_account_uid == bank_account_uid,
                BankConnectionModel.account_id == account_id,
                BankConnectionModel.status != "disconnected",
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_by_account(self, account_id: int) -> list[BankConnection]:
        result = await self._session.execute(
            select(BankConnectionModel).where(
                BankConnectionModel.account_id == account_id
            )
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update_status(self, connection_id: UUID, status: str) -> None:
        await self._session.execute(
            update(BankConnectionModel)
            .where(BankConnectionModel.id == str(connection_id))
            .values(status=status)
        )

    async def update_last_synced(self, connection_id: UUID, synced_at: datetime) -> None:
        await self._session.execute(
            update(BankConnectionModel)
            .where(BankConnectionModel.id == str(connection_id))
            .values(last_synced_at=synced_at)
        )

    @staticmethod
    def _to_entity(row: BankConnectionModel) -> BankConnection:
        return BankConnection(
            id=UUID(str(row.id)),
            account_id=row.account_id,
            user_id=row.user_id,
            session_id=row.session_id,
            bank_name=row.bank_name,
            bank_country=row.bank_country,
            bank_account_uid=row.bank_account_uid,
            bank_account_iban=row.bank_account_iban,
            status=row.status,
            expires_at=row.expires_at,
            last_synced_at=row.last_synced_at,
            created_at=row.created_at,
        )
