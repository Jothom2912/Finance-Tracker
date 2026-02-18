"""
REST API adapter for Goal bounded context.
"""
from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body

from backend.shared.schemas.goal import (
    Goal as GoalSchema,
    GoalCreate,
    GoalBase,
)
from backend.goal.application.service import GoalService
from backend.goal.domain.exceptions import AccountNotFoundForGoal
from backend.auth import get_account_id_from_headers
from backend.dependencies import get_goal_service

router = APIRouter(
    prefix="/goals",
    tags=["Goals"],
)


@router.post(
    "/", response_model=GoalSchema, status_code=status.HTTP_201_CREATED
)
def create_goal(
    goal_data: Dict[str, Any] = Body(...),
    service: GoalService = Depends(get_goal_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
) -> GoalSchema:
    """Opretter et nyt sparemål."""
    if (
        "Account_idAccount" not in goal_data
        or goal_data.get("Account_idAccount") is None
    ):
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account ID mangler.",
            )
        goal_data["Account_idAccount"] = account_id

    try:
        goal = GoalCreate(**goal_data)
        return service.create_goal(goal)
    except AccountNotFoundForGoal as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.get("/", response_model=list[GoalSchema])
def list_goals(
    service: GoalService = Depends(get_goal_service),
    account_id: Optional[int] = Query(None),
    account_id_from_header: Optional[int] = Depends(
        get_account_id_from_headers
    ),
) -> list[GoalSchema]:
    """Henter alle mål for en given konto."""
    final_account_id = account_id or account_id_from_header
    if not final_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler.",
        )
    return service.list_goals(final_account_id)


@router.get("/{goal_id}", response_model=GoalSchema)
def get_goal(
    goal_id: int,
    service: GoalService = Depends(get_goal_service),
) -> GoalSchema:
    """Henter et specifikt mål baseret på ID."""
    goal = service.get_goal(goal_id)
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mål ikke fundet.",
        )
    return goal


@router.put("/{goal_id}", response_model=GoalSchema)
def update_goal(
    goal_id: int,
    goal_data: GoalBase,
    service: GoalService = Depends(get_goal_service),
) -> GoalSchema:
    """Opdaterer et eksisterende mål."""
    updated = service.update_goal(goal_id, goal_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mål ikke fundet.",
        )
    return updated


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    service: GoalService = Depends(get_goal_service),
) -> None:
    """Sletter et mål."""
    if not service.delete_goal(goal_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mål ikke fundet.",
        )
    return None
