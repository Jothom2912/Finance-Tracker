from fastapi import APIRouter, HTTPException, Query, UploadFile, File, status, Header, Depends
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
import pandas as pd

from backend.shared.schemas.transaction import Transaction as TransactionSchema, TransactionCreate
from backend.auth import decode_token
from backend.database.mysql import get_db

# LØSNING: Importer funktioner direkte fra modulet i stedet for pakken.
from backend.services.transaction_service import (
    create_transaction,
    import_transactions_from_csv,
    get_transactions,
    get_transaction_by_id,
    update_transaction,
    delete_transaction
)
from backend.repositories import get_account_repository

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
    print(f"DEBUG _resolve_account_id: x_account_id = {x_account_id} (type: {type(x_account_id)})")

    if x_account_id:
        try:
            account_id = int(x_account_id)
            print(f"DEBUG _resolve_account_id: Konverteret x_account_id til int: {account_id}")
            return account_id
        except ValueError as e:
            print(f"DEBUG _resolve_account_id: Fejl ved konvertering af x_account_id: {e}")
            pass

    if authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            account_repo = get_account_repository(db)
            accounts = account_repo.get_all(user_id=token_data.user_id)
            if accounts:
                account_id = accounts[0]["idAccount"]
                print(f"DEBUG _resolve_account_id: Hentet account_id fra token: {account_id}")
                return account_id

    print(f"DEBUG _resolve_account_id: Returnerer None - ingen account_id fundet")
    return None

# --- Opret manuel transaktion ---
@router.post("/", response_model=TransactionSchema, status_code=status.HTTP_201_CREATED)
def create_transaction_route(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
):
    """Opretter en ny transaktion manuelt."""
    print(f"DEBUG create_transaction_route: x_account_id header = {x_account_id}")
    print(f"DEBUG create_transaction_route: authorization header = {authorization[:50] if authorization else None}...")

    account_id = _resolve_account_id(x_account_id, authorization, db)
    print(f"DEBUG create_transaction_route: resolved account_id = {account_id}")

    if not account_id:
        print(f"DEBUG create_transaction_route: account_id er None - fejler!")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # ✅ DEBUG: Tjek transaction før opdatering
    print(f"DEBUG create_transaction_route: transaction.Account_idAccount BEFORE = {transaction.Account_idAccount}")
    print(f"DEBUG create_transaction_route: transaction input = {transaction.model_dump()}")
    print(f"DEBUG create_transaction_route: transaction input (by_alias=False) = {transaction.model_dump(by_alias=False)}")

    # ✅ FIX: Brug model_copy() med det korrekte feltnavn (Account_idAccount, ikke account_id alias)
    if transaction.Account_idAccount is None:
        # model_copy(update={...}) bruger field navne, ikke aliases
        transaction = transaction.model_copy(update={"Account_idAccount": account_id})
        print(f"DEBUG create_transaction_route: Opdateret transaction med Account_idAccount = {account_id}")

    print(f"DEBUG create_transaction_route: transaction.Account_idAccount AFTER = {transaction.Account_idAccount}")
    print(f"DEBUG create_transaction_route: transaction final = {transaction.model_dump()}")
    print(f"DEBUG create_transaction_route: transaction final (by_alias=False) = {transaction.model_dump(by_alias=False)}")

    try:
        result = create_transaction(transaction, db)
        print(f"DEBUG create_transaction_route: create_transaction returnerede: {result.get('idTransaction') if result else None}")
        # Explicitly validate and convert Dict to TransactionSchema for proper serialization
        return TransactionSchema.model_validate(result)
    except ValueError as e:
        print(f"DEBUG create_transaction_route: ValueError fra create_transaction = {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- CSV Import ---
@router.post("/upload-csv/", response_model=List[TransactionSchema])
async def upload_transactions_csv_route(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
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
        # ✅ FIX: Konverter Dict objekter til Pydantic schemas
        created_transactions = import_transactions_from_csv(contents, account_id, db)
        # Konverter til schemas for response serialization
        return [TransactionSchema.model_validate(t) for t in created_transactions]
    except Exception as e:
        if "EmptyDataError" in str(type(e).__name__):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Den uploadede CSV-fil er tom.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Den uploadede CSV-fil er tom.")
    except (KeyError) as e:
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
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    skip: int = Query(0),
    limit: int = Query(100)
):
    """Henter en liste over transaktioner med filtrering."""
    final_account_id = account_id or _resolve_account_id(x_account_id, authorization, db)

    if not final_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    transactions = get_transactions(
        start_date, end_date, category_id, type, month, year, final_account_id, skip, limit, db
    )
    # Explicitly validate and convert Dict to TransactionSchema for proper serialization
    return [TransactionSchema.model_validate(t) for t in transactions]

# --- Hent specifik transaktion ---
@router.get("/{transaction_id}", response_model=TransactionSchema)
def read_transaction_route(transaction_id: int, db: Session = Depends(get_db)):
    """Henter detaljer for en specifik transaktion baseret på ID."""
    # Kald funktionen direkte
    transaction = get_transaction_by_id(transaction_id, db)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaktion ikke fundet.")
    # Explicitly validate and convert Dict to TransactionSchema for proper serialization
    return TransactionSchema.model_validate(transaction)

# --- Opdater transaktion ---
@router.put("/{transaction_id}", response_model=TransactionSchema)
def update_transaction_route(
    transaction_id: int,
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
):
    """Opdaterer en eksisterende transaktion."""
    account_id = _resolve_account_id(x_account_id, authorization, db)

    # ✅ FIX: Brug model_copy() med det korrekte feltnavn (Account_idAccount, ikke account_id alias)
    if transaction.Account_idAccount is None and account_id:
        transaction = transaction.model_copy(update={"Account_idAccount": account_id})

    try:
        updated = update_transaction(transaction_id, transaction, db)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaktion ikke fundet.")
        # Explicitly validate and convert Dict to TransactionSchema for proper serialization
        return TransactionSchema.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# --- Slet transaktion ---
@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction_route(transaction_id: int, db: Session = Depends(get_db)):
    """Sletter en transaktion."""
    # Kald funktionen direkte
    if not delete_transaction(transaction_id, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaktion ikke fundet.")
    return None
