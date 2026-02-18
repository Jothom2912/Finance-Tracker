"""REST API adapter for Account bounded context."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.shared.schemas.account import (
    Account as AccountSchema,
    AccountCreate,
    AccountBase,
)
from backend.account.application.service import AccountService
from backend.account.domain.exceptions import UserNotFoundForAccount
from backend.auth import get_current_user_id
from backend.dependencies import get_account_service

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)


@router.get("/", response_model=list[AccountSchema])
def list_accounts(
    service: AccountService = Depends(get_account_service),
    user_id: int = Depends(get_current_user_id),
) -> list[AccountSchema]:
    """Henter alle konti tilknyttet den aktuelle bruger."""
    return service.list_accounts(user_id)


@router.get("/{account_id}", response_model=AccountSchema)
def get_account(
    account_id: int,
    service: AccountService = Depends(get_account_service),
    current_user_id: int = Depends(get_current_user_id),
) -> AccountSchema:
    """Henter detaljer for en specifik konto."""
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konto ikke fundet.",
        )

    if account.User_idUser != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Du kan kun se dine egne konti.",
        )

    return account


@router.post(
    "/", response_model=AccountSchema, status_code=status.HTTP_201_CREATED
)
def create_account(
    account_data: AccountBase,
    service: AccountService = Depends(get_account_service),
    user_id: int = Depends(get_current_user_id),
) -> AccountSchema:
    """Opretter en ny konto for den aktuelle bruger."""
    data = AccountCreate(
        name=account_data.name,
        saldo=account_data.saldo,
        User_idUser=user_id,
    )
    try:
        return service.create_account(data)
    except UserNotFoundForAccount as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.put("/{account_id}", response_model=AccountSchema)
def update_account(
    account_id: int,
    account_data: AccountBase,
    service: AccountService = Depends(get_account_service),
    current_user_id: int = Depends(get_current_user_id),
) -> AccountSchema:
    """Opdaterer en konto."""
    existing = service.get_account(account_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konto ikke fundet.",
        )

    if existing.User_idUser != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Du kan kun opdatere dine egne konti.",
        )

    result = service.update_account(account_id, account_data)
    return result
