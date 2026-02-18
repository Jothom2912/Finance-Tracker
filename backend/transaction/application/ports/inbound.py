"""
Inbound ports (driving adapters) for Transaction bounded context.
Defines the service interface for external consumers.
"""
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from backend.transaction.application.dto import (
    PlannedTransactionCreateDTO,
    PlannedTransactionResponseDTO,
    PlannedTransactionUpdateDTO,
    TransactionCreateDTO,
    TransactionResponseDTO,
)


class ITransactionService(ABC):
    """Inbound port defining transaction use cases."""

    @abstractmethod
    def get_transaction(self, transaction_id: int) -> Optional[TransactionResponseDTO]:
        pass

    @abstractmethod
    def list_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        month: Optional[str] = None,
        year: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TransactionResponseDTO]:
        pass

    @abstractmethod
    def create_transaction(
        self, dto: TransactionCreateDTO
    ) -> TransactionResponseDTO:
        pass

    @abstractmethod
    def update_transaction(
        self, transaction_id: int, dto: TransactionCreateDTO
    ) -> Optional[TransactionResponseDTO]:
        pass

    @abstractmethod
    def delete_transaction(self, transaction_id: int) -> bool:
        pass

    @abstractmethod
    def import_from_csv(
        self, file_contents: bytes, account_id: int
    ) -> list[TransactionResponseDTO]:
        pass

    @abstractmethod
    def get_planned_transaction(
        self, pt_id: int
    ) -> Optional[PlannedTransactionResponseDTO]:
        pass

    @abstractmethod
    def list_planned_transactions(
        self, skip: int = 0, limit: int = 100
    ) -> list[PlannedTransactionResponseDTO]:
        pass

    @abstractmethod
    def create_planned_transaction(
        self, dto: PlannedTransactionCreateDTO
    ) -> PlannedTransactionResponseDTO:
        pass

    @abstractmethod
    def update_planned_transaction(
        self, pt_id: int, dto: PlannedTransactionUpdateDTO
    ) -> Optional[PlannedTransactionResponseDTO]:
        pass
