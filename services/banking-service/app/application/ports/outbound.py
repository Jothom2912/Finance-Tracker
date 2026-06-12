from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional, Protocol
from uuid import UUID

from app.domain.entities import BankConnection


class IBankConnectionRepository(Protocol):
    async def save(self, connection: BankConnection) -> BankConnection:
        """Add to session (flush, no commit). Call commit() after batch."""
        ...
    async def commit(self) -> None: ...
    async def get_by_id(self, connection_id: UUID) -> Optional[BankConnection]: ...
    async def get_active_by_uid(
        self, bank_account_uid: str, account_id: int,
    ) -> Optional[BankConnection]:
        """Find non-disconnected connection for this uid+account."""
        ...
    async def list_by_account(self, account_id: int) -> list[BankConnection]: ...
    async def update_status(self, connection_id: UUID, status: str) -> None: ...
    async def update_last_synced(self, connection_id: UUID, synced_at: datetime) -> None: ...


class IPendingAuthorizationRepository(Protocol):
    async def save(self, state: str, account_id: int, user_id: int, expires_at: datetime) -> None:
        """Persist a new pending authorization. Must commit before returning."""
        ...
    async def consume(self, state: str) -> Optional[tuple[int, int]]:
        """Atomically mark state as consumed and return (account_id, user_id).

        Uses UPDATE ... SET consumed_at=now() WHERE state=S AND consumed_at IS NULL
        AND expires_at > now() RETURNING account_id, user_id. Returns None if state
        is unknown, already consumed, or expired. Exactly one concurrent caller wins
        the row lock — replay-safe. Row is preserved for audit (not deleted).

        Called BEFORE the external Enable Banking call. If that call fails, the state
        is consumed and the user must restart the connect flow. This is acceptable
        because auth_codes are single-use — a retry with the same code would fail
        at Enable Banking regardless.
        """
        ...
    async def cleanup_expired(self) -> int:
        """Delete entries that are either expired (never used) or consumed
        more than 24h ago (audit window passed). Returns count deleted.
        """
        ...


class IAccountProjection(Protocol):
    async def get_account_name(self, account_id: int) -> Optional[str]: ...
    async def upsert(self, account_id: int, user_id: int, account_name: str) -> None: ...


class IBankingApiClient(Protocol):
    def get_available_banks(self, country: str = "DK") -> list[dict[str, Any]]: ...
    def start_authorization(self, bank_name: str, country: str = "DK") -> dict[str, str]: ...
    def create_session(self, auth_code: str) -> dict[str, Any]: ...
    def delete_session(self, session_id: str) -> None: ...
    def get_transactions(
        self,
        account_uid: str,
        date_from: Optional[str] = None,
    ) -> tuple[list[Any], int]: ...


class ITransactionImporter(Protocol):
    def bulk_import(
        self,
        user_id: int,
        items: list[Any],
        skip_duplicates: bool = True,
    ) -> Any: ...
