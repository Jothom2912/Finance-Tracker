from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self
from uuid import UUID

from app.domain.entities import Notification


class INotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> Notification:
        """Persist a new notification and return it with id + created_at.

        Raises the underlying ``IntegrityError`` if ``source_key`` already
        exists — the unique constraint is the idempotency backstop.
        """
        ...

    @abstractmethod
    async def source_key_exists(self, source_key: str) -> bool: ...

    @abstractmethod
    async def list_for_user(
        self, user_id: int, *, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        """Newest first, excluding dismissed rows."""
        ...

    @abstractmethod
    async def unread_count(self, user_id: int) -> int: ...

    @abstractmethod
    async def mark_read(self, notification_id: UUID, user_id: int) -> bool:
        """Return True if a row owned by ``user_id`` matched (else 404)."""
        ...

    @abstractmethod
    async def mark_all_read(self, user_id: int) -> int:
        """Return the number of rows moved to read."""
        ...

    @abstractmethod
    async def dismiss(self, notification_id: UUID, user_id: int) -> bool:
        """Soft-delete. Return True if a row owned by ``user_id`` matched."""
        ...


class IEmailPort(ABC):
    @abstractmethod
    async def send(self, *, user_id: int, title: str, body: str) -> None: ...


class IAccountOwnerPort(ABC):
    @abstractmethod
    async def get_owner_user_id(self, account_id: int) -> int:
        """Resolve the user that owns an account.

        Raises ``AccountNotFound`` (404 upstream) or
        ``AccountOwnerUnavailable`` (transport/5xx).
        """
        ...


class IUnitOfWork(ABC):
    notifications: INotificationRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
