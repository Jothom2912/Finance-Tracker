from pydantic import BaseModel, Field
from typing import Optional

class BudgetBase(BaseModel):
    category_id: int = Field(..., description="ID of the category this budget belongs to.")
    amount: float = Field(..., gt=0, description="The budgeted amount for the category.")
    month: str = Field(..., min_length=2, max_length=2, description="Month (MM format, e.g., '01').")
    year: str = Field(..., min_length=4, max_length=4, description="Year (YYYY format, e.g., '2024').")

class BudgetCreate(BudgetBase):
    pass # No additional fields for creation

class BudgetUpdate(BudgetBase):
    # For updates, all fields can be optional
    category_id: Optional[int] = None
    amount: Optional[float] = None
    month: Optional[str] = None
    year: Optional[str] = None

class BudgetInDB(BudgetBase):
    id: int = Field(..., description="Unique ID of the budget.")

    class Config:
        from_attributes = True