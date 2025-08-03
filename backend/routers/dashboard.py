# backend/routers/dashboard.py

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import Dict, List, Any, Optional
from datetime import date, timedelta

from backend.database import get_db, Transaction, Category # Ensure Category is imported
from backend import schemas # Import your schemas, especially FinancialOverview

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

@router.get("/overview/", response_model=schemas.FinancialOverview) # <--- UPDATED response_model
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
    ).all() # .options(joinedload(Transaction.category)).all() # Uncomment if you have a 'category' relationship on Transaction model


    total_income = 0.0
    total_expenses = 0.0
    category_expenses: Dict[str, float] = {}

    for t in transactions_in_period:
        if t.amount > 0:
            total_income += t.amount
        else:
            total_expenses += t.amount # amount is already negative

            category_name = "Ukategoriseret"
            if t.category_id in category_id_to_name:
                category_name = category_id_to_name[t.category_id]
            
            category_expenses[category_name] = category_expenses.get(category_name, 0.0) + abs(t.amount)

    net_change_in_period = total_income + total_expenses

    # Calculate the current total balance across ALL transactions in the database
    # This sums up all transaction amounts, assuming a starting balance of 0.
    # If you have an actual bank account balance, you might fetch it or add an initial balance.
    all_transactions_for_balance = db.query(Transaction).all()
    current_account_balance = sum(t.amount for t in all_transactions_for_balance)


    # Return the data using your Pydantic schema
    return schemas.FinancialOverview(
        start_date=start_date,
        end_date=end_date,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net_change_in_period=round(net_change_in_period, 2),
        expenses_by_category={k: round(v, 2) for k, v in category_expenses.items()},
        current_account_balance=round(current_account_balance, 2) # Included in the schema
    )

# You can add more endpoints here for more specific reports, e.g.
# @router.get("/expenses-by-month/", response_model=List[Dict[str, Any]])
# def get_expenses_by_month(db: Session = Depends(get_db)):
#     """
#     Henter månedsbaserede udgifter.
#     """
#     # Example for aggregation (requires more complex SQLAlchemy queries)
#     # You'd group by month and sum amounts where amount < 0
#     return {"message": "Not implemented yet"}