from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from backend.shared.schemas.account_groups import AccountGroups as AGSchema, AccountGroupsCreate
from backend.services import account_groups_service

router = APIRouter(
    prefix="/account-groups",
    tags=["Account Groups"],
)

@router.post("/", response_model=AGSchema, status_code=status.HTTP_201_CREATED)
def create_group_route(group: AccountGroupsCreate):
    """Opretter en ny kontogruppe."""
    try:
        db_group = account_groups_service.create_group(group)
        return db_group
    except ValueError as e:
        # F.eks. "Mindst én bruger ID er ugyldig."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[AGSchema])
def read_groups_route(skip: int = 0, limit: int = 100):
    """Henter en liste over kontogrupper."""
    return account_groups_service.get_groups(skip=skip, limit=limit)

@router.get("/{group_id}", response_model=AGSchema)
def read_group_route(group_id: int):
    """Henter en kontogruppe baseret på ID."""
    db_group = account_groups_service.get_group_by_id(group_id)
    if db_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kontogruppe ikke fundet.")
    return db_group

@router.put("/{group_id}", response_model=AGSchema)
def update_group_route(group_id: int, group_data: AccountGroupsCreate):
    """Opdaterer en kontogruppe."""
    try:
        updated_group = account_groups_service.update_group(group_id, group_data)
        if updated_group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kontogruppe ikke fundet.")
        return updated_group
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))