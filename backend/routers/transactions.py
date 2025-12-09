from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import pandas as pd 

from backend.database import get_db
from backend.schemas.transaction import Transaction as TransactionSchema, TransactionCreate
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

# --- Opret manuel transaktion ---
@router.post("/", response_model=TransactionSchema, status_code=status.HTTP_201_CREATED)
def create_transaction_route(transaction: TransactionCreate, db: Session = Depends(get_db)):
    """Opretter en ny transaktion manuelt."""
    try:
        # Kald funktionen direkte
        db_transaction = create_transaction(db, transaction)
        return db_transaction
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

    # Hent account_id fra header eller fra user's første account
    account_id = None
    if x_account_id:
        try:
            account_id = int(x_account_id)
        except ValueError:
            pass
    
    # Hvis ingen account_id i header, find første account for brugeren
    if not account_id and authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            from backend.services import account_service
            accounts = account_service.get_accounts_by_user(db, token_data.user_id)
            if accounts:
                account_id = accounts[0].idAccount
    
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    try:
        contents = await file.read()
        # Kald funktionen direkte med account_id
        print(f"📤 Uploading CSV for account_id={account_id}")
        created_transactions = import_transactions_from_csv(db, contents, account_id)
        print(f"✅ Upload complete: {len(created_transactions)} transaktioner gemt")
        return created_transactions
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
    # Hent account_id fra query parameter, header, eller fra user's første account
    final_account_id = account_id
    if not final_account_id and x_account_id:
        try:
            final_account_id = int(x_account_id)
        except ValueError:
            pass
    
    if not final_account_id and authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            from backend.services import account_service
            accounts = account_service.get_accounts_by_user(db, token_data.user_id)
            if accounts:
                final_account_id = accounts[0].idAccount
    
    # Kald funktionen direkte
    transactions = get_transactions(
        db, start_date, end_date, category_id, type, month, year, final_account_id, skip, limit
    )
    return transactions

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
def update_transaction_route(transaction_id: int, transaction: TransactionCreate, db: Session = Depends(get_db)):
    """Opdaterer en eksisterende transaktion."""
    try:
        # Kald funktionen direkte
        updated_transaction = update_transaction(db, transaction_id, transaction)
        if updated_transaction is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaktion ikke fundet.")
        return updated_transaction
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