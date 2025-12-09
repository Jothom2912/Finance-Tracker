from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
from typing import Dict, List, Any, Optional
from datetime import date, timedelta

from backend.models.mysql.transaction import Transaction as TransactionModel
from backend.models.mysql.category import Category as CategoryModel # Denne skal loades
from backend.models.mysql.common import TransactionType # <-- RETTET: Brug den nye 'common' sti
from backend.shared.schemas.dashboard import FinancialOverview
# --- Finansiel Oversigt Funktioner ---

def get_financial_overview(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    account_id: Optional[int] = None
) -> FinancialOverview:
    """Beregner et finansielt overblik for en given periode og account."""

    # KRITISK: account_id er påkrævet
    if not account_id:
        raise ValueError("Account ID er påkrævet for at hente finansielt overblik.")

    # Sæt standard datoer
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    if start_date > end_date:
        raise ValueError("Startdato kan ikke være efter slutdato.")

    # Base filter med account_id (altid påkrævet)
    base_filter = [TransactionModel.Account_idAccount == account_id]

    # 1. Brug database aggregation for at beregne totals (meget hurtigere end at hente alle transaktioner)
    # Beregn total income (positive amounts)
    income_query = db.query(func.sum(TransactionModel.amount)).filter(
        TransactionModel.date >= start_date,
        TransactionModel.date <= end_date,
        TransactionModel.amount > 0
    )
    if base_filter:
        income_query = income_query.filter(*base_filter)
    total_income_result = income_query.scalar()
    total_income = float(total_income_result) if total_income_result else 0.0
    
    # Beregn total expenses (negative amounts)
    expenses_query = db.query(func.sum(TransactionModel.amount)).filter(
        TransactionModel.date >= start_date,
        TransactionModel.date <= end_date,
        TransactionModel.amount < 0
    )
    if base_filter:
        expenses_query = expenses_query.filter(*base_filter)
    total_expenses_result = expenses_query.scalar()
    total_expenses = float(total_expenses_result) if total_expenses_result else 0.0
    
    net_change_in_period = total_income + total_expenses

    # 2. Hent expenses by category (kun for expenses, eager load category)
    expenses_with_categories_query = db.query(
        TransactionModel,
        CategoryModel.name.label('category_name')
    ).join(
        CategoryModel, TransactionModel.Category_idCategory == CategoryModel.idCategory
    ).filter(
        TransactionModel.date >= start_date,
        TransactionModel.date <= end_date,
        TransactionModel.amount < 0
    )
    if base_filter:
        expenses_with_categories_query = expenses_with_categories_query.filter(*base_filter)
    expenses_with_categories = expenses_with_categories_query.all()
    
    category_expenses: Dict[str, float] = {}
    for t, category_name in expenses_with_categories:
        category_name = category_name or "Ukategoriseret"
        amount = abs(float(t.amount))
        category_expenses[category_name] = category_expenses.get(category_name, 0.0) + amount

    # 3. Beregn den nuværende totale saldo (kun for den aktuelle account)
    balance_query = db.query(func.sum(TransactionModel.amount))
    if base_filter:
        balance_query = balance_query.filter(*base_filter)
    total_balance_result = balance_query.scalar()
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