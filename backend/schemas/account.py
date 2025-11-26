from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal

# Forward references for relationships (minimal info)
class UserBase(BaseModel):
    idUser: int
    username: str
    class Config:
        from_attributes = True

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

class GoalBase(BaseModel):
    idGoal: int
    name: Optional[str] = None
    status: Optional[str] = None
    class Config:
        from_attributes = True

# --- Base Schema ---
class AccountBase(BaseModel):
    name: str
    # Brug float i Pydantic til at repræsentere Decimal for JSON-serialisering
    saldo: float = Field(default=0.00, title="Current Account Balance")

# --- Schema for creation (requires User ID) ---
class AccountCreate(AccountBase):
    User_idUser: int

# --- Schema for reading data (includes relationships) ---
class Account(AccountBase):
    idAccount: int
    User_idUser: int
    
    # Relationships
    user: UserBase
    transactions: List[TransactionBase] = []
    budgets: List[BudgetBase] = []
    goals: List[GoalBase] = []

    class Config:
        from_attributes = True
        # Konfigurer Decimal-håndtering (vigtigt for præcisionen fra SQL)
        json_encoders = {
            Decimal: lambda v: float(v),
        }