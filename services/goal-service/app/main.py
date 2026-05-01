from __future__ import annotations

from app.application.dto import GoalBase, GoalCreate
from app.application.ports.inbound import IGoalService
from app.auth import get_current_user_id
from app.dependencies import get_goal_service
from fastapi import Depends, FastAPI, HTTPException

app = FastAPI(title="Goal Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "goal-service"}


@app.get("/api/v1/goals/{goal_id}")
async def get_goal(
    goal_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    goal = await service.get_goal(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.post("/api/v1/goals", status_code=201)
async def create_goal(
    data: GoalCreate,
    _user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    return await service.create_goal(data)


@app.put("/api/v1/goals/{goal_id}")
async def update_goal(
    goal_id: int,
    data: GoalBase,
    _user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    goal = await service.update_goal(goal_id, data)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.delete("/api/v1/goals/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    deleted = await service.delete_goal(goal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")
