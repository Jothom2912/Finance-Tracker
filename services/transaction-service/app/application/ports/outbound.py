from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from contracts.base import BaseEvent

from app.domain.entities import (
    Category,
    OutboxEntry,
    PlannedTransaction,
    SubCategory,
    Transaction,
    TransactionType,
)

# Bank-sync dedup key within one user: (account_id, date, amount, description).
# Matches the cross-service import convention
# ``(user_id, account_id, date, amount, description)`` — user_id is passed
# separately since batches are always single-user.
DedupKey = tuple[int, date, Decimal, str | None]

# Bank-origin idempotency key: (account_id, external_id).  Accounts are
# single-owner, so account_id already scopes the source-system reference;
# a matching partial unique index backstops it in the DB (migration 012).
ExternalIdKey = tuple[int, str]


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
        subcategory_id: int | None = None,
        subcategory_name: str | None = None,
        categorization_tier: str | None = None,
        categorization_confidence: str | None = None,
    ) -> Transaction: ...

    @abstractmethod
    async def find_by_id(self, transaction_id: int, user_id: int) -> Transaction | None: ...

    @abstractmethod
    async def find_filtered(
        self,
        user_id: int,
        account_id: int | None = None,
        category_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        transaction_type: TransactionType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Transaction]: ...

    @abstractmethod
    async def update(self, transaction_id: int, user_id: int, **fields: object) -> Transaction: ...

    @abstractmethod
    async def delete(self, transaction_id: int, user_id: int) -> bool: ...

    @abstractmethod
    async def bulk_create(self, transactions: list[dict]) -> list[Transaction]: ...

    @abstractmethod
    async def find_existing_dedup_keys(
        self,
        user_id: int,
        keys: list[DedupKey],
        *,
        only_missing_external_id: bool = False,
    ) -> set[DedupKey]:
        """Return the subset of ``keys`` that already exist for the user.

        One batch anti-join query instead of a per-row lookup — used by
        the CSV/bulk import paths to skip duplicates.

        With ``only_missing_external_id`` the match is scoped to rows
        whose ``external_id`` IS NULL (legacy/manual/CSV rows).  This is
        the transition fallback for id-bearing bank imports: a fuzzy
        match against a row that carries a *different* external_id must
        NOT dedupe — that is exactly the identical-same-day-purchase
        false positive P2-09 fixes.
        """
        ...

    @abstractmethod
    async def find_existing_external_ids(
        self,
        user_id: int,
        keys: list[ExternalIdKey],
    ) -> set[ExternalIdKey]:
        """Return the subset of ``(account_id, external_id)`` keys that
        already exist for the user — batch anti-join, chunked like
        ``find_existing_dedup_keys``.
        """
        ...


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


class ICategoryRepository(ABC):
    """Read-only access to the event-synced categories read copy.

    Writes happen exclusively in categorization-service (ADR-003); the
    local copy is maintained by the taxonomy sync consumer, which works
    directly on the model — no write methods belong on this port.
    """

    @abstractmethod
    async def find_all(self) -> list[Category]: ...

    @abstractmethod
    async def find_by_id(self, category_id: int) -> Category | None: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> Category | None: ...


class ISubCategoryReadRepository(ABC):
    """Read-only access to the event-synced subcategories read copy."""

    @abstractmethod
    async def find_by_id(self, subcategory_id: int) -> SubCategory | None: ...

    @abstractmethod
    async def find_by_ids(self, subcategory_ids: list[int]) -> dict[int, SubCategory]: ...


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
    categories: ICategoryRepository
    subcategories: ISubCategoryReadRepository
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
