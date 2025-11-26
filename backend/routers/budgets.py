from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

# VIGTIGT: Importér Service laget og dine Pydantic Skemaer
from backend.database import get_db
from backend.schemas.budget import BudgetCreate, BudgetUpdate, BudgetInDB as BudgetSchema, BudgetSummary

# KORREKT: Direkte import af funktionerne
from backend.services.budget_service import (
    get_budgets_by_period, 
    get_budget_by_id, 
    create_budget, 
    update_budget, 
    delete_budget, 
    get_budget_summary
)

router = APIRouter(
    prefix="/budgets",
    tags=["Budgets"],
    responses={404: {"description": "Not found"}},
)

DEFAULT_ACCOUNT_ID = 1

# --- Hentning af Budgetter (Filtreret af måned/år/konto) ---
@router.get("/", response_model=List[BudgetSchema])
async def get_budgets_for_account(
    account_id: int = Query(DEFAULT_ACCOUNT_ID, description="The ID of the account to filter by."), 
    db: Session = Depends(get_db)
):
    """
    Retrieve all budgets for a specific account.
    """
    # RETTET: Kald funktionen direkte
    budgets = get_budgets_by_period(db, account_id=account_id, start_date=None, end_date=None)
    return budgets


# --- Hentning af et specifikt Budget ---
@router.get("/{budget_id}", response_model=BudgetSchema)
async def get_budget_by_id_route( # Omdøbt for at undgå navnekonflikt
    budget_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieve details for a specific budget by its ID.
    """
    # RETTET: Kald funktionen direkte
    budget = get_budget_by_id(db, budget_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


# --- Oprettelse af Budget ---
@router.post("/", response_model=BudgetSchema, status_code=status.HTTP_201_CREATED)
async def create_budget_route(budget: BudgetCreate, db: Session = Depends(get_db)):
    """
    Create a new budget.
    """
    try:
        # RETTET: Kald funktionen direkte
        new_budget = create_budget(db, budget)
        return new_budget
    except ValueError as e:
        if "Integritetsfejl" in str(e) or "ugyldig" in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create budget.")


# --- Opdatering af Budget ---
@router.put("/{budget_id}", response_model=BudgetSchema)
async def update_budget_route(budget_id: int, budget: BudgetUpdate, db: Session = Depends(get_db)):
    """
    Update an existing budget.
    """
    try:
        # RETTET: Kald funktionen direkte
        updated_budget = update_budget(db, budget_id, budget)
        if not updated_budget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
        return updated_budget
    except ValueError as e:
          raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during update.")


# --- Sletning af Budget ---
@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_route(budget_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific budget.
    """
    # RETTET: Kald funktionen direkte
    if not delete_budget(db, budget_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return 


# --- Budget Opsummering ---
@router.get("/summary", response_model=BudgetSummary)
async def get_budget_summary_route(
    month: int = Query(..., description="Month in MM format (e.g., 1).", ge=1, le=12),
    year: int = Query(..., description="Year in YYYY format (e.g., 2024).", ge=2000),
    account_id: int = Query(DEFAULT_ACCOUNT_ID, description="The ID of the account to summarize."),
    db: Session = Depends(get_db)
):
    """
    Generates a detailed budget summary for a specific account, month, and year.
    """
    # RETTET: Kald funktionen direkte
    summary = get_budget_summary(db, account_id, month, year)
    return summary