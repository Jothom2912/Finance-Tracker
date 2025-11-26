from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Dict, List, Any, Optional
from datetime import date, timedelta

from ..models.transaction import Transaction as TransactionModel
from ..models.category import Category as CategoryModel # Denne skal loades
from ..models.common import TransactionType # <-- RETTET: Brug den nye 'common' sti
from ..schemas.dashboard import FinancialOverview
# --- Finansiel Oversigt Funktioner ---

def get_financial_overview(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> FinancialOverview:
    """Beregner et finansielt overblik for en given periode."""

    # Sæt standard datoer
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    if start_date > end_date:
        raise ValueError("Startdato kan ikke være efter slutdato.")

    # 1. Hent alle transaktioner i perioden
    transactions_in_period = db.query(TransactionModel).filter(
        TransactionModel.date >= start_date,
        TransactionModel.date <= end_date
    ).all()

    total_income = 0.0
    total_expenses = 0.0
    category_expenses: Dict[str, float] = {}
    
    # 2. Aggreger indtægter og udgifter pr. kategori
    for t in transactions_in_period:
        amount = float(t.amount)
        if amount > 0:
            total_income += amount
        else:
            total_expenses += amount # amount er negativ
            
            # Find kategorinavnet for udgiften
            category_name = "Ukategoriseret"
            if t.category: # Antager at Category er loaded via relationship, ellers skal det joines.
                category_name = t.category.name
            
            category_expenses[category_name] = category_expenses.get(category_name, 0.0) + abs(amount)

    net_change_in_period = total_income + total_expenses

    # 3. Beregn den nuværende totale saldo (Aggreger over alle transaktioner i databasen)
    total_balance_result = db.query(func.sum(TransactionModel.amount)).scalar()
    current_account_balance = float(total_balance_result) if total_balance_result else 0.0

    # 4. Returner skemaet
    return FinancialOverview(
        start_date=start_date,
        end_date=end_date,
        total_income=round(total_income, 2),
        total_expenses=round(abs(total_expenses), 2), # Returner positivt tal for total udgift
        net_change_in_period=round(net_change_in_period, 2),
        expenses_by_category={k: round(v, 2) for k, v in category_expenses.items()},
        current_account_balance=round(current_account_balance, 2) 
    )

def get_expenses_by_month(
    db: Session, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """Henter månedlige udgifter for en given periode, grupperet efter måned og år."""
    
    if not end_date:
        end_date = date.today()
    if not start_date:
        # Standard til 12 måneder tilbage
        start_date = date(end_date.year - 1, end_date.month, 1)

    if start_date > end_date:
        raise ValueError("Startdato kan ikke være efter slutdato.")

    # Aggreger efter år og måned
    monthly_expenses_query = db.query(
        func.strftime('%Y-%m', TransactionModel.date).label('year_month'),
        func.sum(TransactionModel.amount).label('total_amount')
    ).filter(
        TransactionModel.type == TransactionType.expense.value,
        TransactionModel.date >= start_date,
        TransactionModel.date <= end_date
    ).group_by(
        'year_month'
    ).order_by(
        'year_month'
    ).all()

    # Formater resultaterne
    result = []
    for month_data in monthly_expenses_query:
        result.append({
            "month": month_data.year_month,
            # Sikker på at beløbet er positivt (da vi filtrerede på expense (negativt beløb))
            "total_expenses": round(abs(float(month_data.total_amount)), 2) 
        })
    
    return result