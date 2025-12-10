from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, timedelta
from decimal import Decimal
from backend.validation_boundaries import BUDGET_BVA

class BudgetBase(BaseModel):
    amount: float = Field(
        ...,
        ge=0,  # BVA: amount >= 0
        description="The budgeted amount for the category (must be >= 0)."
    )
    budget_date: Optional[date] = Field(
        default=None,
        description="Budget date"
    )
    Account_idAccount: Optional[int] = Field(None, description="ID of the account this budget belongs to. Optional - backend tilføjer det automatisk.")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """BVA: Amount må være >= 0 (grænse: 0.00 gyldig, -0.01 ugyldig)"""
        if v < 0:
            raise ValueError(f"Amount må være >= 0, fik: {v}")
        return round(v, 2)  # Rund til 2 decimaler

class BudgetCreate(BudgetBase):
    Account_idAccount: Optional[int] = Field(None, description="ID of the account. Optional - backend tilføjer det automatisk fra header.")
    # Support for month/year format from frontend (ikke i modellen, kun for input)
    month: Optional[str] = Field(None, description="Month (MM format) - will be converted to budget_date")
    year: Optional[str] = Field(None, description="Year (YYYY format) - will be converted to budget_date")
    # Support for category_id from frontend (ikke i modellen, kun for input)
    category_id: Optional[int] = Field(None, description="Category ID - will be linked via association table")


class BudgetUpdate(BaseModel):
    # For updates, all fields can be optional
    amount: Optional[float] = None
    budget_date: Optional[date] = None
    Account_idAccount: Optional[int] = None
    # Support for month/year format from frontend
    month: Optional[str] = None
    year: Optional[str] = None
    # Support for category_id from frontend
    category_id: Optional[int] = None

class BudgetInDB(BudgetBase):
    idBudget: int = Field(..., description="Unique ID of the budget.")

    class Config:
        from_attributes = True


# -------- Summary Schemas --------
class BudgetSummaryItem(BaseModel):
    category_id: int
    category_name: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_used: float

class BudgetSummary(BaseModel):
    month: str
    year: str
    items: List[BudgetSummaryItem]
    total_budget: float
    total_spent: float
    total_remaining: float
    over_budget_count: int