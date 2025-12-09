from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.schemas.account import Account as AccountSchema, AccountCreate, AccountBase
from backend.services import account_service
from backend.auth import decode_token

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)

def get_current_user_id(authorization: Optional[str] = Header(None, alias="Authorization")) -> int:
    """Henter user_id fra JWT token i Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header mangler"
        )
    
    # Fjern "Bearer " prefix hvis det findes
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    token_data = decode_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ugyldig eller udløbet token"
        )
    
    return token_data.user_id

@router.post("/", response_model=AccountSchema, status_code=status.HTTP_201_CREATED)
def create_account_route(
    account_data: AccountBase,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Opretter en ny konto for den aktuelle bruger."""
    # Opret AccountCreate med user_id fra token
    account = AccountCreate(
        name=account_data.name,
        saldo=account_data.saldo,
        User_idUser=user_id
    )
    try:
        db_account = account_service.create_account(db, account)
        return db_account
    except ValueError as e:
        # F.eks. "Bruger med dette ID findes ikke."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[AccountSchema])
def read_accounts_route(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Henter alle konti tilknyttet den aktuelle bruger."""
    accounts = account_service.get_accounts_by_user(db, user_id)
    return accounts

@router.get("/{account_id}", response_model=AccountSchema)
def read_account_route(account_id: int, db: Session = Depends(get_db)):
    """Henter detaljer for en specifik konto."""
    db_account = account_service.get_account_by_id(db, account_id)
    if db_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Konto ikke fundet.")
    return db_account

@router.put("/{account_id}", response_model=AccountSchema)
def update_account_route(account_id: int, account_data: AccountBase, db: Session = Depends(get_db)):
    """Opdaterer saldo og navn på en konto."""
    try:
        updated_account = account_service.update_account(db, account_id, account_data)
        if updated_account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Konto ikke fundet.")
        return updated_account
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))