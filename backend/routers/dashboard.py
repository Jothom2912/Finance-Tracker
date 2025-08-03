# backend/routers/dashboard.py

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract # <-- Add func and extract for aggregation
from typing import Dict, List, Any, Optional
from datetime import date, timedelta

from ..database import get_db, Transaction, Category, TransactionType # Ensure Category and TransactionType are imported
from ..schemas.dashboard import FinancialOverview, ExpensesByCategory
from ..schemas.category import Category as CategorySchema # Import the Category schema 

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

@router.get("/overview/", response_model=FinancialOverview)
def get_financial_overview(
    start_date: Optional[date] = Query(None, description="Startdato for oversigt (YYYY-MM-DD). Standard er 30 dage tilbage."),
    end_date: Optional[date] = Query(None, description="Slutdato for oversigt (YYYY-MM-DD). Standard er i dag."),
    db: Session = Depends(get_db)
):
    """
    Henter et finansielt overblik for en given periode.
    Inkluderer total indkomst, total udgift, udgifter fordelt på kategorier og nuværende total saldo.
    """
    # Set default dates if not provided
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Ensure start_date is not after end_date
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Startdato kan ikke være efter slutdato."
        )

    # Fetch all categories once to avoid N+1 queries
    # This creates a dictionary mapping category ID to category name
    all_categories = db.query(Category).all()
    category_id_to_name = {cat.id: cat.name for cat in all_categories}
    
    # Query transactions within the specified date range
    # We load the category relationship if it exists, to ensure efficient access
    transactions_in_period = db.query(Transaction).filter(
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).options(joinedload(Transaction.category)).all() # <-- Uncommented this line


    total_income = 0.0
    total_expenses = 0.0
    category_expenses: Dict[str, float] = {}

    for t in transactions_in_period:
        if t.amount > 0:
            total_income += t.amount
        else:
            total_expenses += t.amount # amount is already negative

            category_name = "Ukategoriseret"
            if t.category: # Prefer category object if loaded
                category_name = t.category.name
            elif t.category_id in category_id_to_name: # Fallback
                category_name = category_id_to_name[t.category_id]
            
            category_expenses[category_name] = category_expenses.get(category_name, 0.0) + abs(t.amount)

    net_change_in_period = total_income + total_expenses

    # Calculate the current total balance across ALL transactions in the database
    all_transactions_for_balance = db.query(Transaction).all()
    current_account_balance = sum(t.amount for t in all_transactions_for_balance)


    # Return the data using your Pydantic schema
    return FinancialOverview(
        start_date=start_date,
        end_date=end_date,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net_change_in_period=round(net_change_in_period, 2),
        expenses_by_category={k: round(v, 2) for k, v in category_expenses.items()},
        current_account_balance=round(current_account_balance, 2) 
    )


# NEW ENDPOINT: Expenses by Month

@router.get("/expenses-by-month/", response_model=List[Dict[str, Any]])
def get_expenses_by_month(
    start_date: Optional[date] = Query(None, description="Startdato for filtrering (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Slutdato for filtrering (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Henter månedlige udgifter for en given periode, grupperet efter måned og år.
    """
    if not end_date:
        end_date = date.today()
    if not start_date:
        # Default til 12 måneder tilbage for månedsoversigt
        start_date = date(end_date.year - 1, end_date.month, 1) if end_date.month > 0 else date(end_date.year - 1, 12, 1)

    # Ensure start_date is not after end_date
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Startdato kan ikke være efter slutdato."
        )

    # Filtrer transaktioner for kun at inkludere udgifter
    # Aggreger efter år og måned
    monthly_expenses = db.query(
        func.strftime('%Y-%m', Transaction.date).label('year_month'), # Formatter dato til 'YYYY-MM'
        func.sum(Transaction.amount).label('total_amount')
    ).filter(
        Transaction.type == TransactionType.expense, # Filter for expenses
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).group_by(
        'year_month' # Group by the formatted year_month string
    ).order_by(
        'year_month' # Order chronologically
    ).all()

    # Formater resultaterne
    result = []
    for month_data in monthly_expenses:
        result.append({
            "month": month_data.year_month,
            "total_expenses": round(abs(month_data.total_amount), 2) # Ensure positive value for expenses
        })
    
    return result