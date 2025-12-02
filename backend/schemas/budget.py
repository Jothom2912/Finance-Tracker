from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, timedelta
from decimal import Decimal
from ..validation_boundaries import BUDGET_BVA

class BudgetBase(BaseModel):
    category_id: int = Field(..., description="ID of the category this budget belongs to.")
    amount: float = Field(
        ...,
        ge=0,  # BVA: amount >= 0
        description="The budgeted amount for the category (must be >= 0)."
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Budget start date"
    )
    end_date: Optional[date] = Field(
        default=None,
        description="Budget end date (must be > start_date)"
    )
    period: str = Field(
        default="monthly",
        description="Budget period: weekly, monthly, or yearly"
    )

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """BVA: Amount må være >= 0 (grænse: 0.00 gyldig, -0.01 ugyldig)"""
        if v < 0:
            raise ValueError(f"Amount må være >= 0, fik: {v}")
        return round(v, 2)  # Rund til 2 decimaler

    @field_validator('period')
    @classmethod
    def validate_period(cls, v: str) -> str:
        """BVA: Period må være weekly, monthly eller yearly"""
        if v not in BUDGET_BVA.valid_periods:
            raise ValueError(f"Period må være en af {BUDGET_BVA.valid_periods}, fik: {v}")
        return v

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v: Optional[date], info) -> Optional[date]:
        """BVA: end_date må være > start_date"""
        if v is not None and 'start_date' in info.data:
            start_date = info.data['start_date']
            if start_date is not None:
                # Grænseværdier:
                # - endDate = startDate (ugyldig)
                # - endDate < startDate (ugyldig)
                # - endDate = startDate + 1 dag (gyldig)
                if v <= start_date:
                    raise ValueError(
                        f"End date må være mindst 1 dag efter start_date. "
                        f"Start: {start_date}, End: {v}"
                    )
        return v

class BudgetCreate(BudgetBase):
    pass  # No additional fields for creation


class BudgetUpdate(BudgetBase):
    # For updates, all fields can be optional
    category_id: Optional[int] = None
    amount: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    period: Optional[str] = None

class BudgetInDB(BudgetBase):
    id: int = Field(..., description="Unique ID of the budget.")

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