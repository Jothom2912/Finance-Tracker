from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto import (
    CopyBudgetRequest,
    MonthlyBudgetCreate,
    MonthlyBudgetResponse,
    MonthlyBudgetSummary,
    MonthlyBudgetUpdate,
)
from app.application.monthly_budget_service import MonthlyBudgetService
from app.auth import get_current_user_id
from app.database import get_db
from app.dependencies import get_monthly_budget_service
from app.domain.exceptions import (
    AccountRequiredForMonthlyBudget,
    CategoryNotFoundForBudgetLine,
    MonthlyBudgetAlreadyClosed,
    MonthlyBudgetAlreadyExists,
    MonthlyBudgetNotFound,
    NoBudgetToCopy,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monthly-budgets", tags=["Monthly Budgets"])


@router.get("/", response_model=MonthlyBudgetResponse | None)
async def get_monthly_budget(
    account_id: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    _user_id: int = Depends(get_current_user_id),
):
    return await service.get_or_none(account_id, month, year)


@router.get("/summary", response_model=MonthlyBudgetSummary)
async def get_monthly_budget_summary(
    account_id: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000),
    budget_start_day: int = Query(1, ge=1, le=28),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.get_summary(account_id, month, year, budget_start_day, user_id=user_id)
    except AccountRequiredForMonthlyBudget as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/", response_model=MonthlyBudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_monthly_budget(
    account_id: int = Query(...),
    dto: MonthlyBudgetCreate = ...,
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.create(account_id, user_id, dto)
    except AccountRequiredForMonthlyBudget as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MonthlyBudgetAlreadyExists as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CategoryNotFoundForBudgetLine as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{budget_id}", response_model=MonthlyBudgetResponse)
async def update_monthly_budget(
    budget_id: int,
    account_id: int = Query(...),
    dto: MonthlyBudgetUpdate = ...,
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    _user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.update(budget_id, account_id, dto)
    except MonthlyBudgetNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CategoryNotFoundForBudgetLine as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monthly_budget(
    budget_id: int,
    account_id: int = Query(...),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    _user_id: int = Depends(get_current_user_id),
):
    if not await service.delete(budget_id, account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")


@router.post("/copy", response_model=MonthlyBudgetResponse, status_code=status.HTTP_201_CREATED)
async def copy_monthly_budget(
    account_id: int = Query(...),
    dto: CopyBudgetRequest = ...,
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.copy_to_month(account_id, user_id, dto)
    except AccountRequiredForMonthlyBudget as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NoBudgetToCopy as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MonthlyBudgetAlreadyExists as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/close", status_code=status.HTTP_204_NO_CONTENT)
async def close_month(
    account_id: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000),
    budget_start_day: int = Query(1, ge=1, le=28),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    try:
        await service.close_month(account_id, year, month, budget_start_day, user_id=user_id)
    except MonthlyBudgetNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MonthlyBudgetAlreadyClosed as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
