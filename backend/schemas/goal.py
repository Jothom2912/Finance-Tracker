from pydantic import BaseModel, Field
from datetime import date
from typing import Optional
from decimal import Decimal

# Forward references for relationships (minimal info)
class AccountBase(BaseModel):
    idAccount: int
    name: str
    class Config:
        from_attributes = True

# --- Base Schema ---
class GoalBase(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: float = Field(default=0.00)
    target_date: Optional[date] = None
    status: Optional[str] = None

# --- Schema for creation (requires Account ID) ---
class GoalCreate(GoalBase):
    Account_idAccount: int

# --- Schema for reading data (includes relationship) ---
class Goal(GoalBase):
    idGoal: int
    Account_idAccount: int
    
    # Relationship
    account: AccountBase

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v),
        }