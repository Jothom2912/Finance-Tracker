# backend/schemas.py
from pydantic import BaseModel
from datetime import date
from typing import List, Optional, Dict

# VIGTIGT: Importér TransactionType direkte fra database.py
# Fjerner afhængigheden til en separat 'models.py' fil
from backend.database import TransactionType # <--- VIGTIG ÆNDRING HER!

class CategoryBase(BaseModel):
    name: str
    type: TransactionType = TransactionType.expense

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int

    class Config:
        from_attributes = True

# --- Transaction Skemaer ---
class TransactionBase(BaseModel):
    description: Optional[str] = None
    amount: float
    date: date
    type: TransactionType = TransactionType.expense
    category_id: Optional[int] = None

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int
    category: Optional[Category] = None

    class Config:
        from_attributes = True

class ExpensesByCategory(BaseModel):
    category_name: str
    amount: float

class FinancialOverview(BaseModel):
    start_date: date
    end_date: date
    total_income: float
    total_expenses: float
    net_change_in_period: float
    # Hvis du beslutter dig for at returnere en liste af objekter:
    # expenses_by_category: List[ExpensesByCategory] 
    # Men Dict[str, float] som i eksemplet ovenfor er også fint og lettere
    expenses_by_category: Dict[str, float] 
    # current_account_balance: Optional[float] = None         