from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, Protocol, Self
from uuid import UUID

from contracts.base import BaseEvent

from app.domain.entities import BankConnection, OutboxEntry


class IBankConnectionRepository(Protocol):
    async def save(self, connection: BankConnection) -> BankConnection:
        """Add to session (flush, no commit)."""
        ...

    async def get_by_id(self, connection_id: UUID) -> Optional[BankConnection]: ...
    async def get_active_by_uid(
        self,
        bank_account_uid: str,
        account_id: int,
    ) -> Optional[BankConnection]:
        """Find non-disconnected connection for this uid+account."""
        ...

    async def list_by_account(self, account_id: int) -> list[BankConnection]: ...
    async def update_status(self, connection_id: UUID, status: str) -> None: ...
    async def update_last_synced(self, connection_id: UUID, synced_at: datetime) -> None: ...
    async def list_active_synced_before(self, cutoff: datetime) -> list[BankConnection]:
        """Active connections never synced or synced before cutoff (F1-05 sweep)."""
        ...

    async def try_claim_sync(self, connection_id: UUID, saga_id: str, now: datetime, ttl_seconds: int) -> bool:
        """Atomic in-flight sync-claim; True iff this caller won (P3-14)."""
        ...

    async def steal_sync_claim(self, connection_id: UUID, old_saga_id: str, new_saga_id: str, now: datetime) -> bool:
        """Take over a known-terminal claim; scoped to old_saga_id (one winner)."""
        ...

    async def clear_sync_claim(self, connection_id: UUID, saga_id: str) -> None:
        """Release the claim iff it still belongs to saga_id."""
        ...

    async def update_consent(
        self,
        connection_id: UUID,
        session_id: str,
        expires_at: Optional[datetime],
    ) -> None:
        """Refresh session + consent expiry after a reconsent (flush, no commit)."""
        ...


class IPendingAuthorizationRepository(Protocol):
    async def save(self, state: str, account_id: int, user_id: int, expires_at: datetime) -> None:
        """Persist a new pending authorization (flush, no commit)."""
        ...

    async def consume(self, state: str) -> Optional[tuple[int, int]]:
        """Atomically mark state as consumed and return (account_id, user_id)."""
        ...

    async def cleanup_expired(self) -> int:
        """Delete expired or stale consumed entries (flush, no commit)."""
        ...


class IAccountProjection(Protocol):
    async def get_account_name(self, account_id: int) -> Optional[str]: ...
    async def get_projection(self, account_id: int) -> Optional[tuple[int, str]]: ...
    async def upsert(self, account_id: int, user_id: int, account_name: str) -> None: ...


class IBankingApiClient(Protocol):
    async def get_available_banks(self, country: str = "DK") -> list[dict[str, Any]]: ...
    async def start_authorization(self, bank_name: str, country: str = "DK") -> dict[str, str]: ...
    async def create_session(self, auth_code: str) -> dict[str, Any]: ...
    async def delete_session(self, session_id: str) -> None: ...
    async def get_transactions(
        self,
        account_uid: str,
        date_from: Optional[str] = None,
    ) -> tuple[list[Any], int]: ...


class IOutboxRepository(ABC):
    @abstractmethod
    async def add(self, event: BaseEvent, aggregate_type: str, aggregate_id: str) -> None: ...

    @abstractmethod
    async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]: ...

    @abstractmethod
    async def mark_published(self, event_id: str) -> None: ...

    @abstractmethod
    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None: ...


class IUnitOfWork(ABC):
    connections: IBankConnectionRepository
    pending_auth: IPendingAuthorizationRepository
    accounts: IAccountProjection
    outbox: IOutboxRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class IAccountPort(ABC):
    @abstractmethod
    async def get_owner_user_id(self, account_id: int) -> int: ...

    @abstractmethod
    async def get_account_info(self, account_id: int) -> tuple[int, str]: ...


class ISagaStatusPort(ABC):
    """Read-only status lookup used by the sync-claim conflict path (P3-14)."""

    @abstractmethod
    async def get_status(self, saga_id: str, bearer_token: str | None) -> str | None:
        """Saga status string, or None when unknown/unreachable (fail-active)."""
        ...
