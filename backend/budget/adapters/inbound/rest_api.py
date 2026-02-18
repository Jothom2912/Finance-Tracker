"""
REST API adapter for Budget bounded context.
Handles HTTP concerns and delegates to application service.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_account_id_from_headers
from backend.dependencies import get_budget_service

from ...application.dto import BudgetCreateDTO, BudgetResponseDTO, BudgetUpdateDTO
from ...application.service import BudgetService
from ...domain.exceptions import (
    AccountRequiredForBudget,
    CategoryNotFoundForBudget,
    CategoryRequiredForBudget,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/budgets",
    tags=["Budgets"],
    responses={404: {"description": "Not found"}},
)


# --- List budgets ---
@router.get("/", response_model=List[BudgetResponseDTO])
async def get_budgets_for_account(
    service: BudgetService = Depends(get_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Retrieve all budgets for a specific account."""
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )

    budgets = service.list_budgets(account_id=account_id)
    return budgets


# --- Get budget by ID ---
@router.get("/{budget_id}", response_model=BudgetResponseDTO)
async def get_budget_by_id_route(
    budget_id: int,
    service: BudgetService = Depends(get_budget_service),
):
    """Retrieve details for a specific budget by its ID."""
    budget = service.get_budget(budget_id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found"
        )
    return budget


# --- Create budget ---
@router.post("/", response_model=BudgetResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_budget_route(
    budget: BudgetCreateDTO,
    service: BudgetService = Depends(get_budget_service),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
):
    """Create a new budget."""
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først.",
        )

    budget_dict = budget.model_dump()
    logger.debug("create_budget_route: budget_dict=%s", budget_dict)

    # Convert month/year to budget_date
    if not budget_dict.get("budget_date"):
        month = budget_dict.get("month")
        year = budget_dict.get("year")
        if month and year:
            try:
                from datetime import date

                budget_dict["budget_date"] = date(int(year), int(month), 1)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ugyldig måned/år: {month}/{year}",
                )

    budget_dict.pop("month", None)
    budget_dict.pop("year", None)

    if (
        "Account_idAccount" not in budget_dict
        or budget_dict.get("Account_idAccount") is None
    ):
        budget_dict["Account_idAccount"] = account_id

    budget_with_account = BudgetCreateDTO(**budget_dict)

    try:
        new_budget = service.create_budget(budget_with_account)
        return new_budget
    except (CategoryNotFoundForBudget, AccountRequiredForBudget, CategoryRequiredForBudget) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except ValueError as e:
        error_msg = str(e)
        if "category_id" in error_msg.lower() or "kategori" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            )
        if "Integritetsfejl" in error_msg or "ugyldig" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create budget: {error_msg}",
        )
    except Exception as e:
        logger.error("create_budget_route: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create budget: {str(e)}",
        )


# --- Update budget ---
@router.put("/{budget_id}", response_model=BudgetResponseDTO)
async def update_budget_route(
    budget_id: int,
    budget: BudgetUpdateDTO,
    service: BudgetService = Depends(get_budget_service),
):
    """Update an existing budget."""
    try:
        budget_dict = budget.model_dump(exclude_unset=True)
        logger.debug("update_budget_route: budget_dict=%s", budget_dict)

        if not budget_dict.get("budget_date"):
            month = budget_dict.get("month")
            year = budget_dict.get("year")
            if month and year:
                try:
                    from datetime import date

                    budget_dict["budget_date"] = date(int(year), int(month), 1)
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ugyldig måned/år: {month}/{year}",
                    )

        budget_dict.pop("month", None)
        budget_dict.pop("year", None)

        budget_with_date = BudgetUpdateDTO(**budget_dict)

        updated_budget = service.update_budget(budget_id, budget_with_date)
        if not updated_budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found"
            )
        return updated_budget
    except CategoryNotFoundForBudget as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during update.",
        )


# --- Delete budget ---
@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_route(
    budget_id: int,
    service: BudgetService = Depends(get_budget_service),
):
    """Delete a specific budget."""
    if not service.delete_budget(budget_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found"
        )
    return
