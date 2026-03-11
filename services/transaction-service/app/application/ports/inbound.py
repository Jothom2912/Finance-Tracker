from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.dto import (
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    CSVImportResultDTO,
    PlannedTransactionResponse,
    TransactionFiltersDTO,
    TransactionResponse,
    UpdatePlannedTransactionDTO,
)


class ITransactionService(ABC):
    @abstractmethod
    async def create_transaction(
        self, user_id: int, dto: CreateTransactionDTO
    ) -> TransactionResponse: ...

    @abstractmethod
    async def get_transaction(
        self, transaction_id: int, user_id: int
    ) -> TransactionResponse: ...

    @abstractmethod
    async def list_transactions(
        self, user_id: int, filters: TransactionFiltersDTO
    ) -> list[TransactionResponse]: ...

    @abstractmethod
    async def delete_transaction(
        self, transaction_id: int, user_id: int
    ) -> None: ...

    @abstractmethod
    async def import_csv(
        self, user_id: int, csv_content: str
    ) -> CSVImportResultDTO: ...

    @abstractmethod
    async def create_planned(
        self, user_id: int, dto: CreatePlannedTransactionDTO
    ) -> PlannedTransactionResponse: ...

    @abstractmethod
    async def list_planned(
        self, user_id: int, active_only: bool = True
    ) -> list[PlannedTransactionResponse]: ...

    @abstractmethod
    async def update_planned(
        self,
        planned_id: int,
        user_id: int,
        dto: UpdatePlannedTransactionDTO,
    ) -> PlannedTransactionResponse: ...

    @abstractmethod
    async def deactivate_planned(
        self, planned_id: int, user_id: int
    ) -> None: ...
