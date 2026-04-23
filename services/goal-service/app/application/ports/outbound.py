"""
Outbound ports (driven adapters) - interfaces for infrastructure.
These define what the Goal application needs from the outside world.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Self

from contracts.base import BaseEvent

from app.domain.entities import Goal, OutboxEntry


class IGoalRepository(ABC):
    """Port for goal persistence."""

    @abstractmethod
    async def get_by_id(self, goal_id: int) -> Optional[Goal]:
        pass

    @abstractmethod
    async def get_all(self, account_id: Optional[int] = None) -> list[Goal]:
        pass

    @abstractmethod
    async def create(self, goal: Goal) -> Goal:
        pass

    @abstractmethod
    async def update(self, goal: Goal) -> Goal:
        pass

    @abstractmethod
    async def delete(self, goal_id: int) -> bool:
        pass


class IAccountPort(ABC):
    """Anti-corruption port for account domain."""

    @abstractmethod
    async def exists(self, user_id: int) -> bool:
        pass


class IOutboxRepository(ABC):
    @abstractmethod
    async def add(
        self,
        event: BaseEvent,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]:
        pass

    @abstractmethod
    async def mark_published(self, event_id: str) -> None:
        pass

    @abstractmethod
    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None:
        pass


class IUnitOfWork(ABC):
    goals: IGoalRepository
    outbox: IOutboxRepository

    @abstractmethod
    async def __aenter__(self) -> Self:
        pass

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        pass

    @abstractmethod
    async def commit(self) -> None:
        pass

    @abstractmethod
    async def rollback(self) -> None:
        pass


class IEventPublisher(ABC):
    @abstractmethod
    async def publish(self, event: BaseEvent) -> None:
        pass
