from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from decimal import Decimal
from backend.validation_boundaries import ACCOUNT_BVA

# Forward references for relationships (minimal info)
class UserBase(BaseModel):
    idUser: int
    username: str
    model_config = ConfigDict(from_attributes=True)

class TransactionBase(BaseModel):
    idTransaction: int
    amount: float
    type: str
    model_config = ConfigDict(from_attributes=True)
        
class BudgetBase(BaseModel):
    idBudget: int
    amount: float
    model_config = ConfigDict(from_attributes=True)

class GoalBase(BaseModel):
    idGoal: int
    name: Optional[str] = None
    status: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# --- Base Schema ---
class AccountBase(BaseModel):
    name: str = Field(
        ...,
        min_length=ACCOUNT_BVA.name_min_length,       # 1 char
        max_length=ACCOUNT_BVA.name_max_length,       # 30 chars
        description="Account name (1-30 characters)"
    )
    saldo: float = Field(
        default=0.00,
        description="Current account balance (can be negative or positive)"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """BVA: Account name må ikke være tomt eller kun mellemrum"""
        if not v or v.strip() == "":
            raise ValueError("Account name må ikke være tomt")
        return v.strip()

    @field_validator('saldo')
    @classmethod
    def validate_saldo(cls, v: float) -> float:
        """BVA: Saldo skal være valideret (kan være negativ eller positiv)"""
        return round(v, 2)

# --- Schema for creation (requires User ID) ---
class AccountCreate(AccountBase):
    User_idUser: int

# --- Schema for reading data (includes relationships) ---
class Account(AccountBase):
    idAccount: int
    User_idUser: Optional[int] = None  # Gør optional (Neo4j returnerer måske None)
    
    # Relationships - alle optional for repository compatibility
    user: Optional[UserBase] = None  # Gør optional (repositories returnerer ikke nested objects)
    transactions: Optional[List[TransactionBase]] = []
    budgets: Optional[List[BudgetBase]] = []
    goals: Optional[List[GoalBase]] = []

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v),
        }
    )