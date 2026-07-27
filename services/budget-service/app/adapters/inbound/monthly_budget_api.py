from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.dto import (
    CopyBudgetRequest,
    MonthlyBudgetCreate,
    MonthlyBudgetResponse,
    MonthlyBudgetSummary,
    MonthlyBudgetUpdate,
)
from app.application.monthly_budget_service import MonthlyBudgetService
from app.auth import get_current_user_id
from app.dependencies import get_monthly_budget_service
from app.domain.exceptions import (
    AccountRequiredForMonthlyBudget,
    CategoryNotFoundForBudgetLine,
    MonthlyBudgetAlreadyClosed,
    MonthlyBudgetAlreadyExists,
    MonthlyBudgetNotFound,
    NoBudgetToCopy,
    UpstreamServiceUnavailable,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monthly-budgets", tags=["Monthly Budgets"])


@router.get("/", response_model=MonthlyBudgetResponse | None)
async def get_monthly_budget(
    account_id: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> MonthlyBudgetResponse | None:
    return await service.get_or_none(account_id, month, year, user_id)


@router.get("/summary", response_model=MonthlyBudgetSummary)
async def get_monthly_budget_summary(
    account_id: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000),
    budget_start_day: int = Query(1, ge=1, le=28),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> MonthlyBudgetSummary:
    try:
        return await service.get_summary(account_id, month, year, budget_start_day, user_id=user_id)
    except AccountRequiredForMonthlyBudget as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/", response_model=MonthlyBudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_monthly_budget(
    dto: MonthlyBudgetCreate,
    account_id: int = Query(...),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> MonthlyBudgetResponse:
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
    dto: MonthlyBudgetUpdate,
    account_id: int = Query(...),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> MonthlyBudgetResponse:
    try:
        return await service.update(budget_id, account_id, user_id, dto)
    except MonthlyBudgetNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CategoryNotFoundForBudgetLine as e:
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
async def delete_monthly_budget(
    budget_id: int,
    account_id: int = Query(...),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> None:
    if not await service.delete(budget_id, account_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")


@router.post("/copy", response_model=MonthlyBudgetResponse, status_code=status.HTTP_201_CREATED)
async def copy_monthly_budget(
    dto: CopyBudgetRequest,
    account_id: int = Query(...),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> MonthlyBudgetResponse:
    try:
        return await service.copy_to_month(account_id, user_id, dto)
    except AccountRequiredForMonthlyBudget as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NoBudgetToCopy as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MonthlyBudgetAlreadyExists as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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
@router.post("/close", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def close_month(
    account_id: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000),
    budget_start_day: int = Query(1, ge=1, le=28),
    service: MonthlyBudgetService = Depends(get_monthly_budget_service),
    user_id: int = Depends(get_current_user_id),
) -> None:
    try:
        await service.close_month(account_id, year, month, budget_start_day, user_id=user_id)
    except MonthlyBudgetNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MonthlyBudgetAlreadyClosed as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except UpstreamServiceUnavailable as e:
        # Fail-closed: uden faktiske udgifter kan overskuddet ikke beregnes —
        # måneden er IKKE lukket, klienten kan prøve igen senere.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
