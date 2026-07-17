from __future__ import annotations

from app.application.dto import (
    AllocationHistoryEntryResponse,
    GoalBase,
    GoalCreate,
    GoalResponse,
    UnallocatedSurplusResponse,
)
from app.application.ports.inbound import IGoalService
from app.auth import get_current_user_id
from app.config import settings
from app.dependencies import get_goal_service
from app.domain.exceptions import AccountNotFoundForGoal, NotAccountOwner, UpstreamServiceUnavailable
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

app = FastAPI(title="Goal Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AccountNotFoundForGoal)
async def account_not_found_handler(_request: Request, exc: AccountNotFoundForGoal) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(NotAccountOwner)
async def not_account_owner_handler(_request: Request, exc: NotAccountOwner) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(UpstreamServiceUnavailable)
async def upstream_unavailable_handler(_request: Request, exc: UpstreamServiceUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "goal-service"}


@app.get("/api/v1/goals", response_model=list[GoalResponse])
async def list_goals(
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
    x_account_id: str = Header(..., alias="X-Account-ID"),
):
    try:
        account_id = int(x_account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Account-ID header")
    return await service.list_goals(account_id, user_id)


# NB: statisk rute FØR /{goal_id}-ruterne — int-path-converteren giver ellers 422.
@app.get("/api/v1/goals/unallocated-surplus", response_model=UnallocatedSurplusResponse)
async def get_unallocated_surplus(
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
    x_account_id: str = Header(..., alias="X-Account-ID"),
):
    try:
        account_id = int(x_account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Account-ID header")
    return await service.get_unallocated_surplus(account_id, user_id)


@app.get("/api/v1/goals/{goal_id}")
async def get_goal(
    goal_id: int,
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    goal = await service.get_goal(goal_id, user_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.get("/api/v1/goals/{goal_id}/allocation-history", response_model=list[AllocationHistoryEntryResponse])
async def get_allocation_history(
    goal_id: int,
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    history = await service.get_allocation_history(goal_id, user_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return history


@app.put("/api/v1/goals/{goal_id}/default", response_model=GoalResponse)
async def set_default_goal(
    goal_id: int,
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    try:
        goal = await service.set_default_goal(goal_id, user_id)
    except IntegrityError:
        # Race mod det partielle unique index (to samtidige set-default);
        # klienten refetcher og prøver igen.
        raise HTTPException(status_code=409, detail="Default goal changed concurrently, retry")
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.delete("/api/v1/goals/{goal_id}/default", response_model=GoalResponse)
async def clear_default_goal(
    goal_id: int,
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    goal = await service.clear_default_goal(goal_id, user_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.post("/api/v1/goals", status_code=201)
async def create_goal(
    data: GoalCreate,
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    return await service.create_goal(data, user_id)


@app.put("/api/v1/goals/{goal_id}")
async def update_goal(
    goal_id: int,
    data: GoalBase,
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    goal = await service.update_goal(goal_id, data, user_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.delete("/api/v1/goals/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: int,
    user_id: int = Depends(get_current_user_id),
    service: IGoalService = Depends(get_goal_service),
):
    deleted = await service.delete_goal(goal_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")
