from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import pandas as pd

from backend.database import get_db
from backend.shared.schemas.transaction import Transaction as TransactionSchema, TransactionCreate
from backend.auth import decode_token

# LØSNING: Importer funktioner direkte fra modulet i stedet for pakken.
from backend.services.transaction_service import (
    create_transaction,
    import_transactions_from_csv,
    get_transactions,
    get_transaction_by_id,
    update_transaction,
    delete_transaction
)

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
)


def _resolve_account_id(
    x_account_id: Optional[str],
    authorization: Optional[str],
    db: Session
) -> Optional[int]:
    """Helper: Hent account_id fra header eller token."""
    if x_account_id:
        try:
            return int(x_account_id)
        except ValueError:
            pass

    if authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            from backend.services import account_service
            accounts = account_service.get_accounts_by_user(db, token_data.user_id)
            if accounts:
                return accounts[0].idAccount
    return None

# --- Opret manuel transaktion ---
@router.post("/", response_model=TransactionSchema, status_code=status.HTTP_201_CREATED)
def create_transaction_route(
    transaction: TransactionCreate,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db)
):
    """Opretter en ny transaktion manuelt."""
    account_id = _resolve_account_id(x_account_id, authorization, db)

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # ✅ FIX: Brug model_copy() i stedet for at oprette ny instans
    if transaction.Account_idAccount is None:
        transaction = transaction.model_copy(update={"account_id": account_id})

    try:
        return create_transaction(db, transaction)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- CSV Import ---
@router.post("/upload-csv/", response_model=List[TransactionSchema])
async def upload_transactions_csv_route(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db)
):
    """Uploader og importerer transaktioner fra en CSV-fil."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ugyldig filtype. Kun CSV-filer er tilladt.")

    account_id = _resolve_account_id(x_account_id, authorization, db)
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    try:
        contents = await file.read()
        # ✅ FIX: Konverter SQLAlchemy objekter til Pydantic schemas
        created_transactions = import_transactions_from_csv(db, contents, account_id)
        # Konverter til schemas for response serialization
        return [TransactionSchema.model_validate(t) for t in created_transactions]
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Den uploadede CSV-fil er tom.")
    except (pd.errors.ParserError, KeyError) as e:
        detail = f"Fejl i CSV-format: {e}. Kontrollér separatorer og kolonner."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Uventet fejl under import: {str(e)}")


# --- Hent transaktioner med filtrering ---
@router.get("/", response_model=List[TransactionSchema])
def read_transactions_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category_id: Optional[int] = Query(None),
    type: Optional[str] = Query(None, description="'income' eller 'expense'"),
    month: Optional[str] = Query(None, min_length=2, max_length=2),
    year: Optional[str] = Query(None, min_length=4, max_length=4),
    account_id: Optional[int] = Query(None),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db)
):
    """Henter en liste over transaktioner med filtrering."""
    final_account_id = account_id or _resolve_account_id(x_account_id, authorization, db)

    if not final_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    return get_transactions(
        db, start_date, end_date, category_id, type, month, year, final_account_id, skip, limit
    )

# --- Hent specifik transaktion ---
@router.get("/{transaction_id}", response_model=TransactionSchema)
def read_transaction_route(transaction_id: int, db: Session = Depends(get_db)):
    """Henter detaljer for en specifik transaktion baseret på ID."""
    # Kald funktionen direkte
    transaction = get_transaction_by_id(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaktion ikke fundet.")
    return transaction

# --- Opdater transaktion ---
@router.put("/{transaction_id}", response_model=TransactionSchema)
def update_transaction_route(
    transaction_id: int,
    transaction: TransactionCreate,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db)
):
    """Opdaterer en eksisterende transaktion."""
    account_id = _resolve_account_id(x_account_id, authorization, db)

    # ✅ FIX: Brug model_copy() i stedet for at oprette ny instans
    if transaction.Account_idAccount is None and account_id:
        transaction = transaction.model_copy(update={"account_id": account_id})

    try:
        updated = update_transaction(db, transaction_id, transaction)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaktion ikke fundet.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# --- Slet transaktion ---
@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction_route(transaction_id: int, db: Session = Depends(get_db)):
    """Sletter en transaktion."""
    # Kald funktionen direkte
    if not delete_transaction(db, transaction_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaktion ikke fundet.")
    return None