from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.schemas.goal import Goal as GoalSchema, GoalCreate, GoalBase
from backend.services import goal_service

router = APIRouter(
    prefix="/goals",
    tags=["Goals"],
)

@router.post("/", response_model=GoalSchema, status_code=status.HTTP_201_CREATED)
def create_goal_route(goal: GoalCreate, db: Session = Depends(get_db)):
    """Opretter et nyt mål tilknyttet en konto."""
    try:
        db_goal = goal_service.create_goal(db, goal)
        return db_goal
    except ValueError as e:
        # F.eks. "Konto med dette ID findes ikke."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[GoalSchema])
def read_goals_route(account_id: int = Query(..., description="Filtrer mål efter konto ID."), db: Session = Depends(get_db)):
    """Henter alle mål tilknyttet en specifik konto."""
    goals = goal_service.get_goals_by_account(db, account_id)
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