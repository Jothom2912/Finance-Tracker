from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from app.domain.entities import Goal, OutboxEntry
from contracts.base import BaseEvent


class IGoalRepository(ABC):
    @abstractmethod
    async def get_by_id(self, goal_id: int) -> Goal | None: ...

    @abstractmethod
    async def get_all(self, account_id: int | None = None) -> list[Goal]: ...

    @abstractmethod
    async def create(self, goal: Goal) -> Goal: ...

    @abstractmethod
    async def update(self, goal: Goal) -> Goal: ...

    @abstractmethod
    async def delete(self, goal_id: int) -> bool: ...


class IAccountPort(ABC):
    @abstractmethod
    async def exists(self, user_id: int) -> bool: ...


class IGoalSavingsRepository(ABC):
    @abstractmethod
    async def get_default_savings_goal(self, account_id: int) -> Goal | None: ...

    @abstractmethod
    async def increment_current_amount(self, goal_id: int, amount: Decimal) -> None: ...


class IGoalAllocationRepository(ABC):
    @abstractmethod
    async def source_key_exists(self, source_key: str) -> bool: ...

    @abstractmethod
    async def add_allocation(
        self,
        *,
        source_key: str,
        goal_id: int,
        account_id: int,
        amount: Decimal,
        correlation_id: str | None,
    ) -> None: ...


class IUnallocatedBudgetSurplusRepository(ABC):
    @abstractmethod
    async def source_key_exists(self, source_key: str) -> bool: ...

    @abstractmethod
    async def add_unallocated(
        self,
        *,
        source_key: str,
        account_id: int,
        amount: Decimal,
        reason: Literal["no_default_goal", "goal_already_complete"],
        correlation_id: str | None,
    ) -> None: ...


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
    goals: IGoalRepository
    outbox: IOutboxRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class IBudgetMonthClosedUnitOfWork(ABC):
    goals: IGoalSavingsRepository
    allocations: IGoalAllocationRepository
    unallocated: IUnallocatedBudgetSurplusRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class IEventPublisher(ABC):
    @abstractmethod
    async def publish(self, event: BaseEvent) -> None: ...
