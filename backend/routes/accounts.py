from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import List, Optional


from backend.shared.schemas.account import Account as AccountSchema, AccountCreate, AccountBase
from backend.services import account_service
from backend.auth import decode_token, get_current_user_id

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)

@router.post("/", response_model=AccountSchema, status_code=status.HTTP_201_CREATED)
def create_account_route(
    account_data: AccountBase,
    user_id: int = Depends(get_current_user_id)
):
    """Opretter en ny konto for den aktuelle bruger."""
    # Opret AccountCreate med user_id fra token
    account = AccountCreate(
        name=account_data.name,
        saldo=account_data.saldo,
        User_idUser=user_id
    )
    try:
        db_account = account_service.create_account(account)
        return db_account
    except ValueError as e:
        # F.eks. "Bruger med dette ID findes ikke."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[AccountSchema])
def read_accounts_route(
    user_id: int = Depends(get_current_user_id)
):
    """Henter alle konti tilknyttet den aktuelle bruger."""
    accounts = account_service.get_accounts_by_user(user_id)
    return accounts

@router.get("/{account_id}", response_model=AccountSchema)
def read_account_route(
    account_id: int, 
    current_user_id: int = Depends(get_current_user_id)
):
    """Henter detaljer for en specifik konto. Kræver authentication og at kontoen tilhører brugeren."""
    db_account = account_service.get_account_by_id(account_id)
    if db_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Konto ikke fundet.")
    
    # Tjek at kontoen tilhører den aktuelle bruger
    if db_account["User_idUser"] != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Du kan kun se dine egne konti."
        )
    
    return db_account

@router.put("/{account_id}", response_model=AccountSchema)
def update_account_route(
    account_id: int, 
    account_data: AccountBase,
    current_user_id: int = Depends(get_current_user_id)
):
    """Opdaterer saldo og navn på en konto. Kræver authentication og at kontoen tilhører brugeren."""
    # Tjek først at kontoen eksisterer og tilhører brugeren
    db_account = account_service.get_account_by_id(account_id)
    if db_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Konto ikke fundet.")
    
    # Tjek at kontoen tilhører den aktuelle bruger
    if db_account["User_idUser"] != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Du kan kun opdatere dine egne konti."
        )
    
    try:
        updated_account = account_service.update_account( account_id, account_data)
        if updated_account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Konto ikke fundet.")
        return updated_account
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))