from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from contracts.base import BaseEvent

from app.domain.entities import (
    OutboxEntry,
    PlannedTransaction,
    Transaction,
    TransactionType,
)


class ITransactionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: int,
        account_id: int,
        account_name: str,
        category_id: int | None,
        category_name: str | None,
        amount: Decimal,
        transaction_type: TransactionType,
        description: str | None,
        tx_date: date,
    ) -> Transaction: ...

    @abstractmethod
    async def find_by_id(self, transaction_id: int, user_id: int) -> Transaction | None: ...

    @abstractmethod
    async def find_by_user(self, user_id: int, skip: int = 0, limit: int = 50) -> list[Transaction]: ...

    @abstractmethod
    async def find_by_account(self, account_id: int, user_id: int) -> list[Transaction]: ...

    @abstractmethod
    async def find_by_category(self, category_id: int, user_id: int) -> list[Transaction]: ...

    @abstractmethod
    async def find_by_date_range(self, user_id: int, start: date, end: date) -> list[Transaction]: ...

    @abstractmethod
    async def delete(self, transaction_id: int, user_id: int) -> bool: ...

    @abstractmethod
    async def bulk_create(self, transactions: list[dict]) -> list[Transaction]: ...


class IPlannedTransactionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: int,
        account_id: int,
        account_name: str,
        category_id: int | None,
        category_name: str | None,
        amount: Decimal,
        transaction_type: TransactionType,
        description: str | None,
        recurrence: str,
        next_execution: date,
    ) -> PlannedTransaction: ...

    @abstractmethod
    async def find_by_id(self, planned_id: int, user_id: int) -> PlannedTransaction | None: ...

    @abstractmethod
    async def find_by_user(self, user_id: int) -> list[PlannedTransaction]: ...

    @abstractmethod
    async def find_active(self, user_id: int) -> list[PlannedTransaction]: ...

    @abstractmethod
    async def update(self, planned_id: int, user_id: int, **fields: object) -> PlannedTransaction: ...

    @abstractmethod
    async def deactivate(self, planned_id: int, user_id: int) -> bool: ...


class IOutboxRepository(ABC):
    """Port for the transactional outbox.

    ``add`` / ``add_batch`` are used by the application service inside
    a UoW transaction.  The remaining methods are used by the outbox
    publisher worker.
    """

    @abstractmethod
    async def add(
        self,
        event: BaseEvent,
        aggregate_type: str,
        aggregate_id: str,
    ) -> None: ...

    @abstractmethod
    async def add_batch(
        self,
        entries: list[tuple[BaseEvent, str, str]],
    ) -> None: ...

    @abstractmethod
    async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]: ...

    @abstractmethod
    async def mark_published(self, event_id: str) -> None: ...

    @abstractmethod
    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None: ...


class IUnitOfWork(ABC):
    """Exposes all repositories sharing one database transaction."""

    transactions: ITransactionRepository
    planned: IPlannedTransactionRepository
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


class IEventPublisher(ABC):
    """Used by the outbox publisher worker only."""

    @abstractmethod
    async def publish(self, event: BaseEvent) -> None: ...
