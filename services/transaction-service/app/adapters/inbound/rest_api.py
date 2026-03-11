from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, UploadFile, status

from app.application.dto import (
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    CSVImportResultDTO,
    PlannedTransactionResponse,
    TransactionFiltersDTO,
    TransactionResponse,
    UpdatePlannedTransactionDTO,
)
from app.application.ports.inbound import ITransactionService
from app.auth import get_current_user_id
from app.dependencies import get_transaction_service
from app.domain.entities import TransactionType

transaction_router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["Transactions"],
)

planned_router = APIRouter(
    prefix="/api/v1/planned-transactions",
    tags=["Planned Transactions"],
)


# ── Transactions ────────────────────────────────────────────────────


@transaction_router.post(
    "/",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    body: CreateTransactionDTO,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    return await service.create_transaction(user_id, body)


@transaction_router.get("/", response_model=list[TransactionResponse])
async def list_transactions(
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
    account_id: int | None = None,
    category_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    transaction_type: TransactionType | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[TransactionResponse]:
    filters = TransactionFiltersDTO(
        account_id=account_id,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        skip=skip,
        limit=limit,
    )
    return await service.list_transactions(user_id, filters)


@transaction_router.get(
    "/{transaction_id}", response_model=TransactionResponse
)
async def get_transaction(
    transaction_id: int,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    return await service.get_transaction(transaction_id, user_id)


@transaction_router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_transaction(
    transaction_id: int,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> None:
    await service.delete_transaction(transaction_id, user_id)


@transaction_router.post(
    "/import-csv", response_model=CSVImportResultDTO
)
async def import_csv(
    file: UploadFile,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> CSVImportResultDTO:
    content = (await file.read()).decode("utf-8")
    return await service.import_csv(user_id, content)


# ── Planned Transactions ────────────────────────────────────────────


@planned_router.post(
    "/",
    response_model=PlannedTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_planned(
    body: CreatePlannedTransactionDTO,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> PlannedTransactionResponse:
    return await service.create_planned(user_id, body)


@planned_router.get("/", response_model=list[PlannedTransactionResponse])
async def list_planned(
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
    active_only: bool = True,
) -> list[PlannedTransactionResponse]:
    return await service.list_planned(user_id, active_only)


@planned_router.patch(
    "/{planned_id}", response_model=PlannedTransactionResponse
)
async def update_planned(
    planned_id: int,
    body: UpdatePlannedTransactionDTO,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> PlannedTransactionResponse:
    return await service.update_planned(planned_id, user_id, body)


@planned_router.delete(
    "/{planned_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def deactivate_planned(
    planned_id: int,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> None:
    await service.deactivate_planned(planned_id, user_id)
