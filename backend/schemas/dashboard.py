from pydantic import BaseModel
from datetime import date
from typing import Dict, List, Optional # Import Optional

class ExpensesByCategory(BaseModel):
    category_name: str
    amount: float

class FinancialOverview(BaseModel):
    start_date: date
    end_date: date
    total_income: float
    total_expenses: float
    net_change_in_period: float
    expenses_by_category: Dict[str, float]
    current_account_balance: Optional[float] = None 
    average_monthly_expenses: Optional[float] = None 