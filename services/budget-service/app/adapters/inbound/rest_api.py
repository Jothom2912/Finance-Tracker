from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dto import BudgetCreateDTO, BudgetResponseDTO, BudgetUpdateDTO
from app.application.ports.inbound import IBudgetService
from app.auth import get_current_user_id
from app.dependencies import get_budget_service
from app.domain.exceptions import (
    AccountRequiredForBudget,
    CategoryNotFoundForBudget,
    CategoryRequiredForBudget,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.get("/", response_model=list[BudgetResponseDTO])
async def list_budgets(
    account_id: int,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> list[BudgetResponseDTO]:
    return await service.list_budgets(account_id=account_id, user_id=user_id)


@router.get("/{budget_id}", response_model=BudgetResponseDTO)
async def get_budget(
    budget_id: int,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> BudgetResponseDTO:
    budget = await service.get_budget(budget_id, user_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


@router.post("/", response_model=BudgetResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_budget(
    dto: BudgetCreateDTO,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> BudgetResponseDTO:
    try:
        return await service.create_budget(user_id, dto)
    except (AccountRequiredForBudget, CategoryRequiredForBudget, CategoryNotFoundForBudget) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{budget_id}", response_model=BudgetResponseDTO)
async def update_budget(
    budget_id: int,
    dto: BudgetUpdateDTO,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> BudgetResponseDTO:
    try:
        result = await service.update_budget(budget_id, user_id, dto)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
        return result
    except CategoryNotFoundForBudget as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# response_model=None is explicit rather than load-bearing, and it is worth knowing
# which: this file has `from __future__ import annotations`, which makes the `-> None`
# return annotation evaluate to NoneType rather than None. FastAPI 0.115.0 read that as
# a real response model and asserted at import time on a 204 -- which is how a green CI
# shipped a container that died at import. Since P2-37 the image installs from uv.lock
# like the tests do, so the two-sources-of-truth split that made it fatal is gone and
# the pinned FastAPI tolerates the annotation. Keep the argument anyway: it states that
# a 204 route has no body, and it is the line that would stop a FastAPI downgrade from
# resurrecting the import error. See
# dev-notes/findings/2026-07-27-none-annotation-204-fastapi-split.md
@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_budget(
    budget_id: int,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> None:
    if not await service.delete_budget(budget_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
