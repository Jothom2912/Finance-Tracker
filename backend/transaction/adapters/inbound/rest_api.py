"""
REST API adapter for Transaction bounded context.
Handles HTTP concerns and delegates to application service.
"""
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from backend.auth import get_account_id_from_headers
from backend.dependencies import get_transaction_service
from backend.transaction.application.dto import (
    PlannedTransactionCreateDTO,
    PlannedTransactionResponseDTO,
    PlannedTransactionUpdateDTO,
    TransactionCreateDTO,
    TransactionResponseDTO,
)
from backend.transaction.application.service import TransactionService
from backend.transaction.domain.exceptions import AccountRequired, CategoryNotFound

logger = logging.getLogger(__name__)

# --- Transaction Router ---

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
)


@router.post(
    "/",
    response_model=TransactionResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction_route(
    transaction: TransactionCreateDTO,
    service: TransactionService = Depends(get_transaction_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Opretter en ny transaktion manuelt."""
    logger.debug("create_transaction_route: account_id = %s", account_id)

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )

    if transaction.Account_idAccount is None:
        transaction = transaction.model_copy(
            update={"Account_idAccount": account_id}
        )

    try:
        return service.create_transaction(transaction)
    except CategoryNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except AccountRequired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID er påkrævet for at oprette en transaktion.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.post("/upload-csv/", response_model=List[TransactionResponseDTO])
async def upload_transactions_csv_route(
    file: UploadFile = File(...),
    service: TransactionService = Depends(get_transaction_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Uploader og importerer transaktioner fra en CSV-fil."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ugyldig filtype. Kun CSV-filer er tilladt.",
        )
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )

    try:
        contents = await file.read()
        return service.import_from_csv(contents, account_id)
    except KeyError as e:
        detail = f"Fejl i CSV-format: {e}. Kontrollér separatorer og kolonner."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=detail
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        if "EmptyDataError" in str(type(e).__name__):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Den uploadede CSV-fil er tom.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Uventet fejl under import: {e!s}",
        )


@router.get("/", response_model=List[TransactionResponseDTO])
def read_transactions_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category_id: Optional[int] = Query(None),
    type: Optional[str] = Query(None, description="'income' eller 'expense'"),
    month: Optional[str] = Query(None, min_length=2, max_length=2),
    year: Optional[str] = Query(None, min_length=4, max_length=4),
    account_id: Optional[int] = Query(None),
    service: TransactionService = Depends(get_transaction_service),
    account_id_from_header: Optional[int] = Depends(get_account_id_from_headers),
    skip: int = Query(0),
    limit: int = Query(100),
):
    """Henter en liste over transaktioner med filtrering."""
    final_account_id = account_id or account_id_from_header

    if not final_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )

    try:
        return service.list_transactions(
            account_id=final_account_id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            tx_type=type,
            month=month,
            year=year,
            skip=skip,
            limit=limit,
        )
    except AccountRequired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )


@router.get("/{transaction_id}", response_model=TransactionResponseDTO)
def read_transaction_route(
    transaction_id: int,
    service: TransactionService = Depends(get_transaction_service),
):
    """Henter detaljer for en specifik transaktion baseret på ID."""
    result = service.get_transaction(transaction_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaktion ikke fundet.",
        )
    return result


@router.put("/{transaction_id}", response_model=TransactionResponseDTO)
def update_transaction_route(
    transaction_id: int,
    transaction: TransactionCreateDTO,
    service: TransactionService = Depends(get_transaction_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Opdaterer en eksisterende transaktion."""
    if transaction.Account_idAccount is None and account_id:
        transaction = transaction.model_copy(
            update={"Account_idAccount": account_id}
        )

    try:
        result = service.update_transaction(transaction_id, transaction)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaktion ikke fundet.",
            )
        return result
    except CategoryNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction_route(
    transaction_id: int,
    service: TransactionService = Depends(get_transaction_service),
):
    """Sletter en transaktion."""
    if not service.delete_transaction(transaction_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaktion ikke fundet.",
        )
    return None


# --- Planned Transaction Router ---

planned_router = APIRouter(
    prefix="/planned-transactions",
    tags=["Planned Transactions"],
)


@planned_router.post(
    "/",
    response_model=PlannedTransactionResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_pt_route(
    pt_data: PlannedTransactionCreateDTO,
    service: TransactionService = Depends(get_transaction_service),
):
    """Opretter en ny planlagt transaktion."""
    try:
        return service.create_planned_transaction(pt_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@planned_router.get("/", response_model=List[PlannedTransactionResponseDTO])
def read_pts_route(
    skip: int = 0,
    limit: int = 100,
    service: TransactionService = Depends(get_transaction_service),
):
    """Henter en liste over planlagte transaktioner."""
    return service.list_planned_transactions(skip=skip, limit=limit)


@planned_router.get("/{pt_id}", response_model=PlannedTransactionResponseDTO)
def read_pt_route(
    pt_id: int,
    service: TransactionService = Depends(get_transaction_service),
):
    """Henter en planlagt transaktion baseret på ID."""
    result = service.get_planned_transaction(pt_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planlagt transaktion ikke fundet.",
        )
    return result


@planned_router.put("/{pt_id}", response_model=PlannedTransactionResponseDTO)
def update_pt_route(
    pt_id: int,
    pt_data: PlannedTransactionUpdateDTO,
    service: TransactionService = Depends(get_transaction_service),
):
    """Opdaterer en planlagt transaktion."""
    try:
        result = service.update_planned_transaction(pt_id, pt_data)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Planlagt transaktion ikke fundet.",
            )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
