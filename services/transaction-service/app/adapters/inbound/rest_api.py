from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Query, UploadFile, status

from app.application.dto import (
    BulkCreateResultDTO,
    BulkCreateTransactionDTO,
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    CSVImportResultDTO,
    PlannedTransactionResponse,
    TransactionFiltersDTO,
    TransactionListResultDTO,
    TransactionResponse,
    UpdatePlannedTransactionDTO,
    UpdateTransactionDTO,
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


# BREAKING (P1-14): the body is an envelope ``{"total_count", "items"}``, not a
# bare array.  A page of rows with no statement of how many rows the filter
# actually matched cannot be told apart from "that is all there was" — the
# defect this endpoint's 50-row default caused twice, on the transactions page
# and in analytics' backfill.  The frontend's tolerant reader landed first
# (``src/api/transactions.jsx``), so there is no deploy window in which an old
# client meets this shape.
@transaction_router.get("/", response_model=TransactionListResultDTO)
async def list_transactions(
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
    account_id: int | None = None,
    category_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    transaction_type: TransactionType | None = None,
    # ``Query(...)`` rather than a bare annotation: a bare ``skip: int = 0``
    # is type-validated by FastAPI but carries no bounds, so ``?limit=201``
    # used to reach ``TransactionFiltersDTO`` inside the handler body and
    # raise ``pydantic.ValidationError`` where FastAPI can no longer
    # translate it — a pure input error surfacing as 500.  The bounds are
    # deliberately duplicated against the DTO's own ``Field`` constraints:
    # these guard the HTTP boundary, those guard construction from
    # non-HTTP callers.  Layered validation, not drift — do not
    # "de-duplicate" either one away.  Mirrors
    # ``analytics-service/app/adapters/inbound/rest_api.py:111-112``.
    #
    # ``le=200`` is a CROSS-SERVICE contract, not just a local guard:
    # analytics' backfill (``app/tools/backfill.py``, ``PAGE_SIZE = 200``)
    # sits exactly on this bound with no margin.  Lowering it makes EVERY
    # backfill page 422 — a full re-index fails, and it fails per-page rather
    # than up front.  Raise it freely; to lower it, lower ``PAGE_SIZE`` first
    # and ship that before this.
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> TransactionListResultDTO:
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


@transaction_router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    return await service.get_transaction(transaction_id, user_id)


@transaction_router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    body: UpdateTransactionDTO,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    return await service.update_transaction(transaction_id, user_id, body)


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


@transaction_router.post("/import-csv", response_model=CSVImportResultDTO)
async def import_csv(
    file: UploadFile,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
    bank_format: str = Form("internal"),
    account_id: int | None = Form(None),
    account_name: str | None = Form(None),
) -> CSVImportResultDTO:
    content = await file.read()
    return await service.import_csv(
        user_id,
        content,
        bank_format=bank_format,
        account_id=account_id,
        account_name=account_name,
    )


@transaction_router.post(
    "/bulk",
    response_model=BulkCreateResultDTO,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_transactions(
    body: BulkCreateTransactionDTO,
    user_id: int = Depends(get_current_user_id),
    service: ITransactionService = Depends(get_transaction_service),
) -> BulkCreateResultDTO:
    """Import a batch of transactions for the authenticated user.

    Used by trusted internal producers (e.g. the banking module's
    bank-sync flow) to hand over pre-categorised transactions.
    Server-side deduplication prevents re-importing the same bank
    transaction when callers retry or the sync is triggered twice.
    """
    return await service.bulk_import(user_id, body)


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


@planned_router.patch("/{planned_id}", response_model=PlannedTransactionResponse)
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
