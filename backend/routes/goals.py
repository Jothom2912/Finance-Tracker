from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Body
from sqlalchemy.orm import Session
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
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db)
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
            accounts = account_service.get_accounts_by_user(db, token_data.user_id)
            if accounts:
                account_id = accounts[0].idAccount

    return account_id

@router.post("/", response_model=GoalSchema, status_code=status.HTTP_201_CREATED)
def create_goal_route(
    goal_data: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db)
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
            accounts = account_service.get_accounts_by_user(db, token_data.user_id)
            if accounts:
                account_id = accounts[0].idAccount

    # Hvis goal_data ikke har account_id, tilføj det fra header/token
    if 'Account_idAccount' not in goal_data or goal_data.get('Account_idAccount') is None:
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account ID mangler. Vælg en konto først."
            )
        goal_data['Account_idAccount'] = account_id
    # Hvis body har Account_idAccount, brug det (frontend sender det korrekt)

    # Valider og opret GoalCreate objekt
    try:
        goal = GoalCreate(**goal_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Valideringsfejl: {str(e)}"
        )

    try:
        db_goal = goal_service.create_goal(db, goal)
        return db_goal
    except ValueError as e:
        # F.eks. "Konto med dette ID findes ikke."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[GoalSchema])
def read_goals_route(
    account_id: Optional[int] = Query(None, description="Filtrer mål efter konto ID."),
    account_id_from_header: Optional[int] = Depends(get_account_id_from_headers),
    db: Session = Depends(get_db)
):
    """Henter alle mål tilknyttet en specifik konto."""
    # Brug account_id fra query parameter, eller fra header hvis ikke angivet
    final_account_id = account_id or account_id_from_header

    if not final_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    goals = goal_service.get_goals_by_account(db, final_account_id)
    return goals

@router.get("/{goal_id}", response_model=GoalSchema)
def read_goal_route(goal_id: int, db: Session = Depends(get_db)):
    """Henter et mål baseret på ID."""
    db_goal = goal_service.get_goal_by_id(db, goal_id)
    if db_goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mål ikke fundet.")
    return db_goal

@router.put("/{goal_id}", response_model=GoalSchema)
def update_goal_route(goal_id: int, goal_data: GoalBase, db: Session = Depends(get_db)):
    """Opdaterer et mål."""
    try:
        updated_goal = goal_service.update_goal(db, goal_id, goal_data)
        if updated_goal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mål ikke fundet.")
        return updated_goal
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal_route(goal_id: int, db: Session = Depends(get_db)):
    """Sletter et mål."""
    try:
        deleted = goal_service.delete_goal(db, goal_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mål ikke fundet.")
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))