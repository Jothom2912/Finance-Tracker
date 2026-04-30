from __future__ import annotations

import logging
from typing import List

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


@router.get("/", response_model=List[BudgetResponseDTO])
async def list_budgets(
    account_id: int,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_budgets(account_id=account_id)


@router.get("/{budget_id}", response_model=BudgetResponseDTO)
async def get_budget(
    budget_id: int,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    budget = await service.get_budget(budget_id, user_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


@router.post("/", response_model=BudgetResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_budget(
    dto: BudgetCreateDTO,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
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
):
    try:
        result = await service.update_budget(budget_id, dto)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
        return result
    except CategoryNotFoundForBudget as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: int,
    service: IBudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    if not await service.delete_budget(budget_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
