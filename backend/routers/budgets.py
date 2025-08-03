# app/routers/budgets.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from backend.database import get_db, Budget, Category, Transaction

from backend.schemas.budgets import BudgetCreate, BudgetUpdate, BudgetInDB

router = APIRouter(
    prefix="/budgets",
    tags=["Budgets"],
    responses={404: {"description": "Not found"}},
)

# --- Eksisterende endpoint (opdateret med bedre fejlhåndtering og typer) ---
@router.get("/", response_model=List[BudgetInDB])
async def get_budgets_by_month_year(
    month: Optional[str] = Query(None, description="Month in MM format (e.g., '01')."),
    year: Optional[str] = Query(None, description="Year in YYYY format (e.g., '2024')."),
    db: Session = Depends(get_db)
):
    """
    Retrieve budgets, optionally filtered by month and year.
    """
    query = db.query(Budget).options(joinedload(Budget.category)) # Load category data
    
    if month:
        query = query.filter(Budget.month == month)
    if year:
        query = query.filter(Budget.year == year)
    
    budgets = query.all()
    if not budgets and (month or year):
        # Hvis der ikke er budgetter for en specifik periode, er det ikke en fejl, men bare ingen data.
        # Men hvis der slet ingen budgetter er, kan man overveje en tom liste.
        pass # Return empty list if no budgets found for the filter

    return budgets

# --- NYT ENDPOINT: Hent alle budgetter for et specifikt år ---
@router.get("/yearly/{year}", response_model=List[BudgetInDB])
async def get_budgets_for_year(
    year: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve all budgets for a specific year.
    """
    # Load category data for each budget to avoid N+1 queries if you need category details
    budgets = db.query(Budget).options(joinedload(Budget.category)).filter(Budget.year == year).all()
    if not budgets:
        # Returnerer en tom liste, hvis der ikke er budgetter for året,
        # hvilket typisk er bedre end en 404 for en samling.
        return []
    return budgets

# --- NYT ENDPOINT: Hent detaljer for et specifikt budget ---
@router.get("/{budget_id}", response_model=BudgetInDB)
async def get_budget_by_id(
    budget_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieve details for a specific budget by its ID.
    """
    budget = db.query(Budget).options(joinedload(Budget.category)).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget

# --- Eksisterende POST endpoint (kun som reference, behold din egen) ---
@router.post("/", response_model=BudgetInDB, status_code=status.HTTP_201_CREATED)
async def create_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    # Tjek for duplikat FØRST
    existing_budget = db.query(Budget).filter(
        Budget.category_id == budget.category_id,
        Budget.month == budget.month,
        Budget.year == budget.year
    ).first()
    if existing_budget:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, # 409 Conflict er passende for duplicate ressource
            detail="Budget for this category in the specified month/year already exists."
        )
    
    db_budget = Budget(**budget.model_dump())
    try:
        db.add(db_budget)
        db.commit()
        db.refresh(db_budget)
        # Reload budget with category relationship for the response
        db_budget_with_category = db.query(Budget).options(joinedload(Budget.category)).filter(Budget.id == db_budget.id).first()
        return db_budget_with_category
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create budget due to data integrity issue.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

# --- Eksisterende PUT endpoint (kun som reference, behold din egen) ---
@router.put("/{budget_id}", response_model=BudgetInDB)
async def update_budget(budget_id: int, budget: BudgetUpdate, db: Session = Depends(get_db)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not db_budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    update_data = budget.model_dump(exclude_unset=True) # Only update provided fields

    # Check for duplicate if category_id, month, or year are being changed
    if 'category_id' in update_data or 'month' in update_data or 'year' in update_data:
        new_category_id = update_data.get('category_id', db_budget.category_id)
        new_month = update_data.get('month', db_budget.month)
        new_year = update_data.get('year', db_budget.year)
        
        existing_duplicate = db.query(Budget).filter(
            Budget.category_id == new_category_id,
            Budget.month == new_month,
            Budget.year == new_year,
            Budget.id != budget_id # Exclude the current budget being updated
        ).first()

        if existing_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another budget for this category in the specified month/year already exists."
            )

    for key, value in update_data.items():
        setattr(db_budget, key, value)
    
    try:
        db.add(db_budget)
        db.commit()
        db.refresh(db_budget)
        # Reload budget with category relationship for the response
        db_budget_with_category = db.query(Budget).options(joinedload(Budget.category)).filter(Budget.id == db_budget.id).first()
        return db_budget_with_category
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

# --- Eksisterende DELETE endpoint (kun som reference, behold din egen) ---
@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not db_budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    db.delete(db_budget)
    db.commit()
    return # 204 No Content for successful deletion