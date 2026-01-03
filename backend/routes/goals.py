from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Body
from typing import List, Optional, Dict, Any

from backend.database import get_db
from backend.shared.schemas.goal import Goal as GoalSchema, GoalCreate, GoalBase
from backend.services import goal_service
from backend.auth import decode_token

router = APIRouter(
    prefix="/goals",
    tags=["Goals"],
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
                account_id = accounts[0].idAccount

    return account_id

@router.post("/", response_model=GoalSchema, status_code=status.HTTP_201_CREATED)
def create_goal_route(
    goal: GoalCreate,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
):
    """Opretter et nyt mål tilknyttet en konto."""
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

    # Set account_id on goal if not already set
    if goal.Account_idAccount is None:
        goal = goal.model_copy(update={"Account_idAccount": account_id})

    try:
        db_goal = goal_service.create_goal(goal)
        return db_goal
    except ValueError as e:
        # F.eks. "Konto med dette ID findes ikke."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[GoalSchema])
def read_goals_route(
    account_id: Optional[int] = Query(None, description="Filtrer mål efter konto ID."),
    account_id_from_header: Optional[int] = Depends(get_account_id_from_headers)
):
    """Henter alle mål tilknyttet en specifik konto."""
    # Brug account_id fra query parameter, eller fra header hvis ikke angivet
    final_account_id = account_id or account_id_from_header

    if not final_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    goals = goal_service.get_goals_by_account(final_account_id)
    return goals

@router.get("/{goal_id}", response_model=GoalSchema)
def read_goal_route(goal_id: int):
    """Henter et mål baseret på ID."""
    db_goal = goal_service.get_goal_by_id(goal_id)
    if db_goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mål ikke fundet.")
    return db_goal

@router.put("/{goal_id}", response_model=GoalSchema)
def update_goal_route(goal_id: int, goal_data: GoalBase):
    """Opdaterer et mål."""
    try:
        updated_goal = goal_service.update_goal(goal_id, goal_data)
        if updated_goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mål ikke fundet.")
        return updated_goal
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal_route(goal_id: int):
    """Sletter et mål."""
    try:
        deleted = goal_service.delete_goal(goal_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mål ikke fundet.")
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))