"""
REST API adapter for MonthlyBudget bounded context.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth import get_account_id_from_headers
from backend.dependencies import get_monthly_budget_service
from backend.monthly_budget.application.dto import (
    CopyBudgetRequest,
    MonthlyBudgetCreate,
    MonthlyBudgetResponse,
    MonthlyBudgetSummary,
    MonthlyBudgetUpdate,
)
from backend.monthly_budget.application.service import MonthlyBudgetService
from backend.monthly_budget.domain.exceptions import (
    AccountRequiredForMonthlyBudget,
    CategoryNotFoundForBudgetLine,
    MonthlyBudgetAlreadyExists,
    MonthlyBudgetNotFound,
    NoBudgetToCopy,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/monthly-budgets",
    tags=["Monthly Budgets"],
    responses={404: {"description": "Not found"}},
)


def _require_account(account_id: Optional[int]) -> int:
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )
    return account_id


# ── Summary (before parametric routes) ──────────────────────────


@router.get("/summary", response_model=MonthlyBudgetSummary)
async def get_monthly_budget_summary(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=9999),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Budget vs. actual spending summary for a month."""
    aid = _require_account(account_id)
    return service.get_summary(aid, month, year)


# ── CRUD ─────────────────────────────────────────────────────────


@router.get("/", response_model=Optional[MonthlyBudgetResponse])
async def get_monthly_budget(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=9999),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Get the monthly budget for a period, or null if none exists."""
    aid = _require_account(account_id)
    result = service.get_or_none(aid, month, year)
    return result


@router.post(
    "/",
    response_model=MonthlyBudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_monthly_budget(
    body: MonthlyBudgetCreate,
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Create a new monthly budget with lines."""
    aid = _require_account(account_id)
    try:
        return service.create(aid, body)
    except MonthlyBudgetAlreadyExists as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    except CategoryNotFoundForBudgetLine as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/{budget_id}", response_model=MonthlyBudgetResponse)
async def update_monthly_budget(
    budget_id: int,
    body: MonthlyBudgetUpdate,
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Replace all lines in an existing monthly budget."""
    aid = _require_account(account_id)
    try:
        return service.update(budget_id, aid, body)
    except MonthlyBudgetNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CategoryNotFoundForBudgetLine as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monthly_budget(
    budget_id: int,
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Delete a monthly budget and all its lines."""
    aid = _require_account(account_id)
    if not service.delete(budget_id, aid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Budget not found")


# ── Copy ─────────────────────────────────────────────────────────


@router.post(
    "/copy",
    response_model=MonthlyBudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def copy_monthly_budget(
    body: CopyBudgetRequest,
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Copy budget lines from one month to another."""
    aid = _require_account(account_id)
    try:
        return service.copy_to_month(aid, body)
    except NoBudgetToCopy as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except MonthlyBudgetAlreadyExists as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
