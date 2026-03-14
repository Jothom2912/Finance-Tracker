from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Self

from contracts.base import BaseEvent

from app.domain.entities import OutboxEntry, User, UserWithCredentials


class IUserRepository(ABC):
    """Port for user persistence."""

    @abstractmethod
    async def create(
        self, username: str, email: str, password_hash: str
    ) -> UserWithCredentials: ...

    @abstractmethod
    async def find_by_email(self, email: str) -> UserWithCredentials | None: ...

    @abstractmethod
    async def find_by_username(
        self, username: str
    ) -> UserWithCredentials | None: ...

    @abstractmethod
    async def find_by_id(self, user_id: int) -> User | None: ...


class IEventPublisher(ABC):
    """Port for publishing domain events to the message broker.

    Used by the outbox publisher worker — no longer called directly
    from application services.
    """

    @abstractmethod
    async def publish(self, event: BaseEvent) -> None: ...


class IOutboxRepository(ABC):
    """Port for the transactional outbox.

    Application services call ``add()`` within a UoW transaction.
    The outbox publisher worker calls ``fetch_pending``,
    ``mark_published``, and ``mark_failed``.
    """

    @abstractmethod
    async def add(
        self,
        event: BaseEvent,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None: ...

    @abstractmethod
    async def fetch_pending(
        self, batch_size: int = 10
    ) -> list[OutboxEntry]: ...

    @abstractmethod
    async def mark_published(self, event_id: str) -> None: ...

    @abstractmethod
    async def mark_failed(
        self, event_id: str, next_attempt_at: datetime
    ) -> None: ...


class IUnitOfWork(ABC):
    """Port for transactional boundaries.

    Exposes repositories so all writes share the same database
    transaction.  Use as an async context manager::

        async with uow:
            await uow.users.create(...)
            await uow.outbox.add(event, ...)
            await uow.commit()
    """

    users: IUserRepository
    outbox: IOutboxRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
