from __future__ import annotations

from abc import ABC, abstractmethod

from contracts.base import BaseEvent

from app.domain.entities import User, UserWithCredentials


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
    """Port for publishing domain events to the message broker."""

    @abstractmethod
    async def publish(self, event: BaseEvent) -> None: ...
