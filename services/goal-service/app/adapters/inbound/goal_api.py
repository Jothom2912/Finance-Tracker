"""REST API adapter for Goal bounded context."""

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.application.dto import (
    Goal as GoalSchema,
)
from app.application.dto import (
    GoalBase,
    GoalCreate,
)
from app.application.ports.inbound import IGoalService
from app.dependencies import get_goal_service
from app.domain.exceptions import AccountNotFoundForGoal

router = APIRouter(
    prefix="/goals",
    tags=["Goals"],
)
@router.post("/", response_model=GoalSchema, status_code=status.HTTP_201_CREATED)
async def create_goal(
    goal_data: dict[str, Any] = Body(...),
    service: IGoalService = Depends(get_goal_service),
    account_id: Optional[int] = Depends(lambda: None),  # TODO: Replace with JWT-based user resolution
) -> GoalSchema:
    """Opretter et nyt sparemål."""
    if "user_id" in goal_data and "Account_idAccount" not in goal_data:
        goal_data["Account_idAccount"] = goal_data["user_id"]

    if "Account_idAccount" not in goal_data or goal_data.get("Account_idAccount") is None:
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account ID mangler.",
            )
        goal_data["Account_idAccount"] = account_id

    try:
        goal = GoalCreate(**goal_data)
        return await service.create_goal(goal)
    except AccountNotFoundForGoal as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=list[GoalSchema])
async def list_goals(
    service: IGoalService = Depends(get_goal_service),
    account_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    account_id_from_header: Optional[int] = Depends(lambda: None),  # TODO: Implement with real auth
) -> list[GoalSchema]:
    """Henter alle mål for en given konto."""
    final_account_id = user_id or account_id or account_id_from_header
    if not final_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler.",
        )
    return await service.list_goals(final_account_id)


@router.get("/{goal_id}", response_model=GoalSchema)
async def get_goal(
    goal_id: int,
    service: IGoalService = Depends(get_goal_service),
) -> GoalSchema:
    """Henter et specifikt mål baseret på ID."""
    goal = await service.get_goal(goal_id)
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mål ikke fundet.",
        )
    return goal


@router.put("/{goal_id}", response_model=GoalSchema)
async def update_goal(
    goal_id: int,
    goal_data: GoalBase,
    service: IGoalService = Depends(get_goal_service),
) -> GoalSchema:
    """Opdaterer et eksisterende mål."""
    updated = await service.update_goal(goal_id, goal_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mål ikke fundet.",
        )
    return updated


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: int,
    service: IGoalService = Depends(get_goal_service),
) -> None:
    """Sletter et mål."""
    if not await service.delete_goal(goal_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mål ikke fundet.",
        )
