"""Outbound ports for the Categorization bounded context.

Repository ports use ABC (explicit implementation required).
Pipeline tier ports use Protocol (structural subtyping).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Protocol, Self

from contracts.base import BaseEvent

from app.domain.entities import (
    CategorizationResultRecord,
    CategorizationRule,
    Category,
    Merchant,
    OutboxEntry,
    SubCategory,
)
from app.domain.value_objects import CategorizationResult, CategoryType


class ICategoryRepository(ABC):
    @abstractmethod
    async def create(self, name: str, category_type: CategoryType, display_order: int = 0) -> Category: ...

    @abstractmethod
    async def find_all(self) -> list[Category]: ...

    @abstractmethod
    async def find_by_id(self, category_id: int) -> Optional[Category]: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[Category]: ...

    @abstractmethod
    async def update(self, category_id: int, **fields: object) -> Category: ...

    @abstractmethod
    async def delete(self, category_id: int) -> bool: ...


class ISubCategoryRepository(ABC):
    @abstractmethod
    async def create(self, name: str, category_id: int, is_default: bool = True) -> SubCategory: ...

    @abstractmethod
    async def find_all(self) -> list[SubCategory]: ...

    @abstractmethod
    async def find_by_id(self, subcategory_id: int) -> Optional[SubCategory]: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[SubCategory]: ...

    @abstractmethod
    async def find_by_category_id(self, category_id: int) -> list[SubCategory]: ...

    @abstractmethod
    async def delete(self, subcategory_id: int) -> bool: ...


class IMerchantRepository(ABC):
    @abstractmethod
    async def save(self, merchant: Merchant) -> Merchant: ...

    @abstractmethod
    async def find_by_id(self, merchant_id: int) -> Optional[Merchant]: ...

    @abstractmethod
    async def find_by_normalized_name(self, name: str) -> Optional[Merchant]: ...

    @abstractmethod
    async def find_by_subcategory_id(self, subcategory_id: int) -> list[Merchant]: ...


class IRuleRepository(ABC):
    @abstractmethod
    async def find_active_rules(self, user_id: int | None = None) -> list[CategorizationRule]: ...

    @abstractmethod
    async def create(self, rule: CategorizationRule) -> CategorizationRule: ...

    @abstractmethod
    async def update(self, rule_id: int, **fields: object) -> CategorizationRule: ...

    @abstractmethod
    async def delete(self, rule_id: int) -> bool: ...


class ICategorizationResultRepository(ABC):
    @abstractmethod
    async def save(self, record: CategorizationResultRecord) -> CategorizationResultRecord: ...

    @abstractmethod
    async def find_by_transaction_id(self, transaction_id: int) -> list[CategorizationResultRecord]: ...


class IOutboxRepository(ABC):
    @abstractmethod
    async def add(self, event: BaseEvent, aggregate_type: str, aggregate_id: str) -> None: ...

    @abstractmethod
    async def add_batch(self, entries: list[tuple[BaseEvent, str, str]]) -> None: ...

    @abstractmethod
    async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]: ...

    @abstractmethod
    async def mark_published(self, event_id: str) -> None: ...

    @abstractmethod
    async def mark_failed(self, event_id: str, next_attempt_at: datetime) -> None: ...


class IUnitOfWork(ABC):
    categories: ICategoryRepository
    subcategories: ISubCategoryRepository
    merchants: IMerchantRepository
    rules: IRuleRepository
    results: ICategorizationResultRepository
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


# ── Pipeline tier ports (Protocol — structural subtyping) ──


class IRuleEngine(Protocol):
    """Tier 1: deterministic keyword/rule matching."""

    def match(self, description: str, amount: float) -> CategorizationResult | None: ...


class IMlCategorizer(Protocol):
    """Tier 2: ML-based prediction."""

    def predict(self, description: str) -> CategorizationResult | None: ...


class ILlmCategorizer(Protocol):
    """Tier 3: LLM-based fallback."""

    def predict(self, description: str, amount: float) -> CategorizationResult: ...

    def predict_batch(self, transactions: list[tuple[str, float]]) -> list[CategorizationResult]: ...
