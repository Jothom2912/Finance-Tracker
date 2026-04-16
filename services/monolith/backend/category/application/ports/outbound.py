"""
Outbound ports (driven adapters) for Category bounded context.

Defines interfaces for infrastructure dependencies.
Each port corresponds to one aggregate or entity in the domain.

Repository ports use ABC (need explicit implementation).
Tier ports use Protocol (structural subtyping, looser coupling).

ID types are int throughout. If microservice split requires UUID,
swap in the adapter implementations — domain stays unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Protocol

from backend.category.domain.entities import Category, Merchant, SubCategory
from backend.category.domain.value_objects import CategorizationResult, MerchantMapping


# ──────────────────────────────────────────────
# Repository ports (ABC — explicit implementation)
# ──────────────────────────────────────────────


class ICategoryRepository(ABC):
    """Read-only port over the Category projection.

    Writes to the Category projection are the sole responsibility
    of :class:`backend.consumers.category_sync.CategorySyncConsumer`
    in response to events from ``transaction-service``.
    """

    @abstractmethod
    def get_by_id(self, category_id: int) -> Optional[Category]:
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Category]:
        pass

    @abstractmethod
    def get_all(self) -> list[Category]:
        pass


class ISubCategoryRepository(ABC):
    """Port for subcategory persistence."""

    @abstractmethod
    def get_by_id(self, subcategory_id: int) -> Optional[SubCategory]:
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[SubCategory]:
        pass

    @abstractmethod
    def get_by_category_id(self, category_id: int) -> list[SubCategory]:
        pass

    @abstractmethod
    def get_all(self) -> list[SubCategory]:
        pass

    @abstractmethod
    def create(self, subcategory: SubCategory) -> SubCategory:
        pass

    @abstractmethod
    def delete(self, subcategory_id: int) -> bool:
        pass


class IMerchantRepository(ABC):
    """Port for learned merchant entities."""

    @abstractmethod
    def find_by_normalized_name(self, name: str) -> Optional[Merchant]:
        pass

    @abstractmethod
    def get_by_id(self, merchant_id: int) -> Optional[Merchant]:
        pass

    @abstractmethod
    def get_by_subcategory_id(self, subcategory_id: int) -> list[Merchant]:
        pass

    @abstractmethod
    def save(self, merchant: Merchant) -> Merchant:
        pass


class IMerchantMappingRepository(ABC):
    """Port for keyword -> merchant/subcategory rule mappings."""

    @abstractmethod
    def find_by_keyword(self, keyword: str) -> Optional[MerchantMapping]:
        pass

    @abstractmethod
    def find_best_match(self, description: str) -> Optional[MerchantMapping]:
        """Search all mappings for longest keyword match in description."""
        pass

    @abstractmethod
    def get_all(self) -> list[MerchantMapping]:
        pass

    @abstractmethod
    def save(self, mapping: MerchantMapping) -> None:
        pass


# ──────────────────────────────────────────────
# Pipeline tier ports (Protocol — structural subtyping)
# ──────────────────────────────────────────────


class IRuleEngine(Protocol):
    """Tier 1: deterministic keyword matching."""

    def match(
        self, description: str, amount: float
    ) -> CategorizationResult | None:
        """Return None if no keyword matches."""
        ...


class IMlCategorizer(Protocol):
    """Tier 2: ML-based prediction."""

    def predict(self, description: str) -> CategorizationResult | None:
        """Return None if confidence is below threshold."""
        ...


class ILlmCategorizer(Protocol):
    """
    Tier 3: LLM-based fallback.

    Separate from ICategorizationPort (orchestrator port).
    This port is narrow: predict single + predict batch.
    """

    def predict(
        self, description: str, amount: float
    ) -> CategorizationResult:
        """Always returns a result (fallback to 'Anden')."""
        ...

    def predict_batch(
        self, transactions: list[tuple[str, float]]
    ) -> list[CategorizationResult]:
        """Batch prediction — more efficient for CSV import."""
        ...


# ──────────────────────────────────────────────
# Orchestrator port
# ──────────────────────────────────────────────


class ICategorizationPort(ABC):
    """
    Orchestrator port for the categorization pipeline.

    The implementation runs: rules -> ML -> LLM fallback
    and returns a CategorizationResult.
    """

    @abstractmethod
    def categorize(self, description: str, amount: float) -> CategorizationResult:
        pass
