"""REST API adapter for AccountGroup bounded context."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.shared.schemas.account_groups import (
    AccountGroups as AccountGroupSchema,
    AccountGroupsCreate,
)
from backend.account.application.service import AccountService
from backend.account.domain.exceptions import InvalidUserInGroup
from backend.dependencies import get_account_service

router = APIRouter(
    prefix="/account-groups",
    tags=["Account Groups"],
)


@router.get("/", response_model=list[AccountGroupSchema])
def list_groups(
    skip: int = 0,
    limit: int = 100,
    service: AccountService = Depends(get_account_service),
) -> list[AccountGroupSchema]:
    """Henter en liste over kontogrupper."""
    return service.list_groups(skip=skip, limit=limit)


@router.get("/{group_id}", response_model=AccountGroupSchema)
def get_group(
    group_id: int,
    service: AccountService = Depends(get_account_service),
) -> AccountGroupSchema:
    """Henter en kontogruppe baseret på ID."""
    group = service.get_group(group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kontogruppe ikke fundet.",
        )
    return group


@router.post(
    "/",
    response_model=AccountGroupSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_group(
    group_data: AccountGroupsCreate,
    service: AccountService = Depends(get_account_service),
) -> AccountGroupSchema:
    """Opretter en ny kontogruppe."""
    try:
        return service.create_group(group_data)
    except InvalidUserInGroup as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.put("/{group_id}", response_model=AccountGroupSchema)
def update_group(
    group_id: int,
    group_data: AccountGroupsCreate,
    service: AccountService = Depends(get_account_service),
) -> AccountGroupSchema:
    """Opdaterer en kontogruppe."""
    try:
        result = service.update_group(group_id, group_data)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kontogruppe ikke fundet.",
            )
        return result
    except InvalidUserInGroup as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
