from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from typing import List, Optional

from backend.database import get_db
from backend.shared.schemas.planned_transactions import PlannedTransactions as PTSchema, PlannedTransactionsCreate, PlannedTransactionsBase
from backend.services import planned_transactions_service
from backend.auth import decode_token

router = APIRouter(
    prefix="/planned-transactions",
    tags=["Planned Transactions"],
)

def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
) -> Optional[int]:
    """Henter account_id fra X-Account-ID header eller fra user's første account."""
    account_id = None

    # Først prøv at hente fra X-Account-ID header
    if x_account_id:
        try:
            account_id = int(x_account_id)
            return account_id
        except ValueError:
            pass

    # Hvis ikke fundet, prøv at hente fra user's første account
    if not account_id and authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            from backend.services import account_service
            accounts = account_service.get_accounts_by_user( token_data.user_id)
            if accounts:
                account_id = accounts[0]["idAccount"]

    return account_id

@router.post("/", response_model=PTSchema, status_code=status.HTTP_201_CREATED)
def create_pt_route(
    pt_data: PlannedTransactionsCreate,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
):
    """Opretter en ny planlagt transaktion."""
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
            accounts = account_service.get_accounts_by_user(token_data.user_id)
            if accounts:
                account_id = accounts[0]["idAccount"]

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # Set account_id on pt_data if not already set
    if pt_data.Account_idAccount is None:
        pt_data = pt_data.model_copy(update={"Account_idAccount": account_id})

    try:
        db_pt = planned_transactions_service.create_planned_transaction(pt_data)
        return db_pt
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[PTSchema])
def read_pts_route(
    skip: int = 0, 
    limit: int = 100,
    account_id: Optional[int] = Depends(get_account_id_from_headers)
):
    """Henter en liste over planlagte transaktioner."""
    return planned_transactions_service.get_planned_transactions(account_id=account_id, skip=skip, limit=limit)

@router.get("/{pt_id}", response_model=PTSchema)
def read_pt_route(pt_id: int):
    """Henter en planlagt transaktion baseret på ID."""
    db_pt = planned_transactions_service.get_planned_transaction_by_id(pt_id)
    if db_pt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planlagt transaktion ikke fundet.")
    return db_pt

@router.put("/{pt_id}", response_model=PTSchema)
def update_pt_route(pt_id: int, pt_data: PlannedTransactionsBase):
    """Opdaterer en planlagt transaktion."""
    try:
        updated_pt = planned_transactions_service.update_planned_transaction(pt_id, pt_data)
        if updated_pt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planlagt transaktion ikke fundet.")
        return updated_pt
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))