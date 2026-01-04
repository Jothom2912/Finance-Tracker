from typing import Dict, List, Any, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session
from backend.repositories import get_transaction_repository, get_category_repository
from backend.shared.schemas.dashboard import FinancialOverview

# --- Finansiel Oversigt Funktioner ---

def get_financial_overview(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    account_id: Optional[int] = None,
    db: Session = None
) -> FinancialOverview:
    """Beregner et finansielt overblik for en given periode og account."""

    # KRITISK: account_id er påkrævet
    if not account_id:
        raise ValueError("Account ID er påkrævet for at hente finansielt overblik.")
    
    if db is None:
        raise ValueError("db: Session parameter is required")

    # Sæt standard datoer
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    if start_date > end_date:
        raise ValueError("Startdato kan ikke være efter slutdato.")

    transaction_repo = get_transaction_repository(db)
    category_repo = get_category_repository(db)
    
    # Hent alle transaktioner for perioden
    transactions = transaction_repo.get_all(
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        limit=10000  # Høj limit for at få alle
    )
    
    # Beregn totals
    total_income = 0.0
    total_expenses = 0.0
    category_expenses: Dict[str, float] = {}
    current_account_balance = 0.0
    
    # Hent alle kategorier for at mappe ID til navn
    categories = category_repo.get_all()
    category_id_to_name = {cat.get("idCategory"): cat.get("name") for cat in categories if cat.get("idCategory")}
    
    for t in transactions:
        amount = float(t.get("amount", 0))
        current_account_balance += amount
        
        if amount > 0:
            total_income += amount
        else:
            total_expenses += abs(amount)
            
            # Gruppér expenses by category
            category_id = t.get("Category_idCategory")
            if category_id:
                category_name = category_id_to_name.get(category_id, "Ukategoriseret")
                category_expenses[category_name] = category_expenses.get(category_name, 0.0) + abs(amount)
    
    net_change_in_period = total_income - total_expenses

    # 4. Returner skemaet
    return FinancialOverview(
        start_date=start_date,
        end_date=end_date,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net_change_in_period=round(net_change_in_period, 2),
        expenses_by_category={k: round(v, 2) for k, v in category_expenses.items()},
        current_account_balance=round(current_account_balance, 2)
    )

def get_expenses_by_month(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None,
    account_id: Optional[int] = None,
    db: Session = None
) -> List[Dict[str, Any]]:
    """Henter månedlige udgifter for en given periode, grupperet efter måned og år."""
    
    if not end_date:
        end_date = date.today()
    if not start_date:
        # Standard til 12 måneder tilbage
        start_date = date(end_date.year - 1, end_date.month, 1)

    if start_date > end_date:
        raise ValueError("Startdato kan ikke være efter slutdato.")
    
    if db is None:
        raise ValueError("db: Session parameter is required")

    transaction_repo = get_transaction_repository(db)
    
    # Hent alle transaktioner for perioden
    transactions = transaction_repo.get_all(
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        limit=10000
    )
    
    # Filtrer kun expenses (negative amounts eller type == 'expense')
    expenses = [t for t in transactions if float(t.get("amount", 0)) < 0 or t.get("type", "").lower() == "expense"]
    
    # Gruppér efter måned
    monthly_expenses: Dict[str, float] = {}
    
    for expense in expenses:
        t_date = expense.get("date")
        if t_date:
            # Konverter til date objekt hvis det er string
            if isinstance(t_date, str):
                try:
                    from datetime import datetime
                    t_date = datetime.fromisoformat(t_date.replace('Z', '+00:00')).date()
                except:
                    continue
            elif hasattr(t_date, 'date'):
                t_date = t_date.date()
            
            year_month = f"{t_date.year}-{t_date.month:02d}"
            amount = abs(float(expense.get("amount", 0)))
            monthly_expenses[year_month] = monthly_expenses.get(year_month, 0.0) + amount
    
    # Formater resultaterne
    result = []
    for month, total in sorted(monthly_expenses.items()):
        result.append({
            "month": month,
            "total_expenses": round(total, 2)
        })
    
    return result
