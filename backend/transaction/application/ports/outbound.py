"""
Outbound ports (driven adapters) for Transaction bounded context.
Defines interfaces for infrastructure dependencies.
"""
from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, Optional

from backend.transaction.domain.entities import (
    CategoryInfo,
    PlannedTransaction,
    Transaction,
)


class ITransactionRepository(ABC):
    """Port for transaction persistence."""

    @abstractmethod
    def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        pass

    @abstractmethod
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Transaction]:
        pass

    @abstractmethod
    def create(self, transaction: Transaction) -> Transaction:
        pass

    @abstractmethod
    def update(self, transaction: Transaction) -> Optional[Transaction]:
        pass

    @abstractmethod
    def delete(self, transaction_id: int) -> bool:
        pass

    @abstractmethod
    def search(
        self,
        search_text: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
    ) -> list[Transaction]:
        pass

    @abstractmethod
    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict:
        """Returns aggregated summary as dict (analytics projection)."""
        pass


class IPlannedTransactionRepository(ABC):
    """Port for planned transaction persistence."""

    @abstractmethod
    def get_by_id(self, pt_id: int) -> Optional[PlannedTransaction]:
        pass

    @abstractmethod
    def get_all(self, skip: int = 0, limit: int = 100) -> list[PlannedTransaction]:
        pass

    @abstractmethod
    def create(self, planned: PlannedTransaction) -> PlannedTransaction:
        pass

    @abstractmethod
    def update(self, planned: PlannedTransaction) -> Optional[PlannedTransaction]:
        pass


class ICategoryPort(ABC):
    """Anti-corruption port for category domain lookups."""

    @abstractmethod
    def get_by_id(self, category_id: int) -> Optional[CategoryInfo]:
        pass

    @abstractmethod
    def get_all(self) -> list[CategoryInfo]:
        pass

    @abstractmethod
    def create(self, name: str, category_type: str) -> CategoryInfo:
        pass
