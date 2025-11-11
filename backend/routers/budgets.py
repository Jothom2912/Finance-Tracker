# app/routers/budgets.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from backend.database import get_db, Budget, Category, Transaction

from backend.schemas.budgets import BudgetCreate, BudgetUpdate, BudgetInDB, BudgetSummary, BudgetSummaryItem

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

# --- NEW: Summary endpoint for month/year ---
@router.get("/summary", response_model=BudgetSummary)
async def get_budget_summary(
    month: str = Query(..., description="Month in MM format (e.g., '01')."),
    year: str = Query(..., description="Year in YYYY format (e.g., '2024')."),
    db: Session = Depends(get_db)
):
    print(f"DEBUG: month={month}, year={year}")  # Tilføj debug-log
    # Fjern midlertidigt validering for at teste om det løser 422-fejlen
    # if len(month) != 2 or not month.isdigit() or not (1 <= int(month) <= 12):
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid month. Use MM format like '01'.")
    # if len(year) != 4 or not year.isdigit():
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid year. Use YYYY format like '2024'.")

    # Fetch budgets for month/year
    budgets = db.query(Budget).options(joinedload(Budget.category)).filter(
        Budget.month == month,
        Budget.year == year
    ).all()

    # Compute expenses by category for month/year
    # Using Transaction.date for month/year matching via SQLite strftime for compatibility
    expenses_by_category = dict(
        db.query(
            Transaction.category_id,
            func.sum(Transaction.amount)
        ).filter(
            extract('month', Transaction.date) == int(month),
            extract('year', Transaction.date) == int(year),
            Transaction.amount < 0
        ).group_by(Transaction.category_id).all()
    )

    items: list[BudgetSummaryItem] = []
    total_budget = 0.0
    total_spent = 0.0
    over_budget_count = 0

    for b in budgets:
        spent = abs(expenses_by_category.get(b.category_id, 0.0))
        remaining = b.amount - spent
        percentage_used = (spent / b.amount * 100.0) if b.amount > 0 else 0.0
        if remaining < 0:
            over_budget_count += 1
        items.append(BudgetSummaryItem(
            category_id=b.category_id,
            category_name=b.category.name if b.category else "Ukendt",
            budget_amount=round(b.amount, 2),
            spent_amount=round(spent, 2),
            remaining_amount=round(remaining, 2),
            percentage_used=round(percentage_used, 2)
        ))
        total_budget += b.amount
        total_spent += spent

    total_remaining = total_budget - total_spent

    # Include categories that have expenses but no budget for the period
    if expenses_by_category:
        budget_category_ids = {b.category_id for b in budgets}
        category_ids_with_expense = {cid for cid in expenses_by_category.keys() if cid is not None}
        missing_budget_category_ids = category_ids_with_expense - budget_category_ids

        if missing_budget_category_ids:
            # Fetch names for these categories
            categories = db.query(Category).filter(Category.id.in_(missing_budget_category_ids)).all()
            id_to_name = {c.id: c.name for c in categories}
            for cid in missing_budget_category_ids:
                spent = abs(expenses_by_category.get(cid, 0.0) or 0.0)
                items.append(BudgetSummaryItem(
                    category_id=cid,
                    category_name=id_to_name.get(cid, "Ukendt"),
                    budget_amount=0.0,
                    spent_amount=round(spent, 2),
                    remaining_amount=round(-spent, 2),
                    percentage_used=100.0
                ))

    return BudgetSummary(
        month=month,
        year=year,
        items=items,
        total_budget=round(total_budget, 2),
        total_spent=round(total_spent, 2),
        total_remaining=round(total_remaining, 2),
        over_budget_count=over_budget_count
    )

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