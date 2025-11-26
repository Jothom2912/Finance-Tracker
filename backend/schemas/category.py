from pydantic import BaseModel
from typing import List

# Forward references for relationships (minimal info)
class TransactionBase(BaseModel):
    idTransaction: int
    amount: float
    type: str
    class Config:
        from_attributes = True

class BudgetBase(BaseModel):
    idBudget: int
    amount: float
    class Config:
        from_attributes = True


# --- Base Schema ---
class CategoryBase(BaseModel):
    name: str
    type: str

# --- Schema for creation ---
class CategoryCreate(CategoryBase):
    pass

# --- Schema for reading data ---
class Category(CategoryBase):
    idCategory: int
    
    # Relationships
    transactions: List[TransactionBase] = []
    budgets: List[BudgetBase] = []

    class Config:
        from_attributes = True