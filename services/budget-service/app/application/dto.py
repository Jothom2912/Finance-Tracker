from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BudgetCreateDTO(BaseModel):
    amount: float = Field(..., ge=0)
    budget_date: Optional[date] = None
    month: Optional[int] = None
    year: Optional[int] = None
    account_id: int
    category_id: int

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Amount må være >= 0, fik: {v}")
        return round(v, 2)


class BudgetUpdateDTO(BaseModel):
    amount: Optional[float] = None
    budget_date: Optional[date] = None
    month: Optional[int] = None
    year: Optional[int] = None
    category_id: Optional[int] = None


class BudgetResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    budget_date: Optional[date]
    account_id: int
    category_id: int
