from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import BankConnection
from app.models.bank_connection import BankConnectionModel


def _to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Strip tz at the persistence boundary.

    Application code works with timezone-aware UTC datetimes; the
    columns are ``TIMESTAMP WITHOUT TIME ZONE`` filled with UTC
    wall-clock time (repo-wide convention), and asyncpg rejects aware
    values for them.
    """
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


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
            expires_at=_to_naive_utc(connection.expires_at),
        )
        self._session.add(row)
        await self._session.flush()
        connection.created_at = row.created_at
        return connection

    async def get_by_id(self, connection_id: UUID) -> Optional[BankConnection]:
        result = await self._session.execute(
            select(BankConnectionModel).where(BankConnectionModel.id == str(connection_id))
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_active_by_uid(
        self,
        bank_account_uid: str,
        account_id: int,
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
            select(BankConnectionModel).where(BankConnectionModel.account_id == account_id)
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update_status(self, connection_id: UUID, status: str) -> None:
        await self._session.execute(
            update(BankConnectionModel).where(BankConnectionModel.id == str(connection_id)).values(status=status)
        )

    async def update_last_synced(self, connection_id: UUID, synced_at: datetime) -> None:
        await self._session.execute(
            update(BankConnectionModel)
            .where(BankConnectionModel.id == str(connection_id))
            .values(last_synced_at=_to_naive_utc(synced_at))
        )

    async def try_claim_sync(
        self,
        connection_id: UUID,
        saga_id: str,
        now: datetime,
        ttl_seconds: int,
    ) -> bool:
        """Atomic in-flight claim (P3-14): wins iff no claim exists or the
        existing one is older than the TTL backstop. Exactly one concurrent
        caller gets rowcount 1."""
        naive_now = _to_naive_utc(now)
        cutoff = naive_now - timedelta(seconds=ttl_seconds)
        result = await self._session.execute(
            update(BankConnectionModel)
            .where(
                BankConnectionModel.id == str(connection_id),
                or_(
                    BankConnectionModel.sync_started_at.is_(None),
                    BankConnectionModel.sync_started_at < cutoff,
                ),
            )
            .values(sync_saga_id=saga_id, sync_started_at=naive_now)
        )
        return result.rowcount == 1

    async def steal_sync_claim(
        self,
        connection_id: UUID,
        old_saga_id: str,
        new_saga_id: str,
        now: datetime,
    ) -> bool:
        """Take over a claim whose saga is known-terminal. Scoped to the old
        saga_id so only one of several concurrent stealers wins."""
        result = await self._session.execute(
            update(BankConnectionModel)
            .where(
                BankConnectionModel.id == str(connection_id),
                BankConnectionModel.sync_saga_id == old_saga_id,
            )
            .values(sync_saga_id=new_saga_id, sync_started_at=_to_naive_utc(now))
        )
        return result.rowcount == 1

    async def clear_sync_claim(self, connection_id: UUID, saga_id: str) -> None:
        """Release only our own claim — a newer saga's claim must survive."""
        await self._session.execute(
            update(BankConnectionModel)
            .where(
                BankConnectionModel.id == str(connection_id),
                BankConnectionModel.sync_saga_id == saga_id,
            )
            .values(sync_saga_id=None, sync_started_at=None)
        )

    async def update_consent(
        self,
        connection_id: UUID,
        session_id: str,
        expires_at: Optional[datetime],
    ) -> None:
        await self._session.execute(
            update(BankConnectionModel)
            .where(BankConnectionModel.id == str(connection_id))
            .values(session_id=session_id, expires_at=_to_naive_utc(expires_at))
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
            sync_saga_id=row.sync_saga_id,
            sync_started_at=row.sync_started_at,
            created_at=row.created_at,
        )
