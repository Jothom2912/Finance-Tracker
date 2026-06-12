from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pending_authorization import PendingAuthorizationModel


class PostgresPendingAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        state: str,
        account_id: int,
        user_id: int,
        expires_at: datetime,
    ) -> None:
        row = PendingAuthorizationModel(
            id=uuid4(),
            state=state,
            account_id=account_id,
            user_id=user_id,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.commit()

    async def consume(self, state: str) -> Optional[tuple[int, int]]:
        result = await self._session.execute(
            text("""
                UPDATE pending_authorizations
                SET consumed_at = now()
                WHERE state = :state
                  AND consumed_at IS NULL
                  AND expires_at > now()
                RETURNING account_id, user_id
            """),
            {"state": state},
        )
        row = result.fetchone()
        if row is None:
            return None
        await self._session.commit()
        return (row.account_id, row.user_id)

    async def cleanup_expired(self) -> int:
        now = datetime.utcnow()
        audit_cutoff = now - timedelta(hours=24)
        result = await self._session.execute(
            delete(PendingAuthorizationModel).where(
                (PendingAuthorizationModel.expires_at < now)
                | (PendingAuthorizationModel.consumed_at < audit_cutoff)
            )
        )
        await self._session.commit()
        return result.rowcount
