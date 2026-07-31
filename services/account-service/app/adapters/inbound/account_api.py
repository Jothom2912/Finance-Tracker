"""REST API adapter for Account bounded context."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dto import (
    Account as AccountSchema,
)
from app.application.dto import (
    AccountBase,
    AccountCreate,
)
from app.application.service import AccountService
from app.auth import get_current_user_id
from app.dependencies import get_account_service
from app.domain.exceptions import UserNotFoundForAccount

logger = logging.getLogger(__name__)

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
        # P3-59, fravalg: den ordinære 404 får ingen linje.  Access-linjen siger allerede
        # metode, sti og statuskode, og der er ikke mere at sige.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konto ikke fundet.",
        )

    if account.User_idUser != current_user_id:
        # P3-59: 403'en er tvetydig på den måde der betyder noget — den kan være en helt
        # normal bruger hvis frontend holder et forældet konto-id, eller et bruger-til-bruger
        # opslag.  Statuskoden skelner ikke, men *ophobning på samme token* gør, og det
        # kræver at forsøget efterlader et spor.  Bemærk at 404'en ovenfor rammer først, så
        # en 403 her betyder at kontoen findes og tilhører en anden — ikke et blindt gæt.
        logger.warning(
            "Afvist læsning af fremmed konto: bruger %s forsøgte konto %s (ejet af %s)",
            current_user_id,
            account_id,
            account.User_idUser,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Du kan kun se dine egne konti.",
        )

    return account


@router.post("/", response_model=AccountSchema, status_code=status.HTTP_201_CREATED)
def create_account(
    account_data: AccountBase,
    service: AccountService = Depends(get_account_service),
    user_id: int = Depends(get_current_user_id),
) -> AccountSchema:
    """Opretter en ny konto for den aktuelle bruger."""
    data = AccountCreate(
        name=account_data.name,
        saldo=account_data.saldo,
        budget_start_day=account_data.budget_start_day,
        User_idUser=user_id,
    )
    try:
        return service.create_account(data)
    except UserNotFoundForAccount as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
        # Samme tvetydighed som på GET, men et skriveforsøg — derfor står den som sit eget
        # kald med sin egen ordlyd frem for en delt hjælpefunktion: det er forskellen på et
        # forældet konto-id i en liste og et forsøg på at overskrive en fremmed konto, og
        # den forskel skal kunne læses direkte i loggen.
        logger.warning(
            "Afvist opdatering af fremmed konto: bruger %s forsøgte konto %s (ejet af %s)",
            current_user_id,
            account_id,
            existing.User_idUser,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Du kan kun opdatere dine egne konti.",
        )

    result = service.update_account(account_id, account_data)
    return result
