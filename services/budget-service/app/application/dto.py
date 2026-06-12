from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# -- Legacy Budget DTOs -------------------------------------------------------


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


# -- Monthly Budget DTOs ------------------------------------------------------


class BudgetLineCreate(BaseModel):
    category_id: int
    amount: float = Field(ge=0)


class MonthlyBudgetCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=9999)
    lines: list[BudgetLineCreate] = Field(default_factory=list)


class MonthlyBudgetUpdate(BaseModel):
    lines: list[BudgetLineCreate]


class CopyBudgetRequest(BaseModel):
    source_month: int = Field(ge=1, le=12)
    source_year: int = Field(ge=2000, le=9999)
    target_month: int = Field(ge=1, le=12)
    target_year: int = Field(ge=2000, le=9999)


class BudgetLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    category_name: Optional[str] = None
    amount: float


class MonthlyBudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    month: int
    year: int
    lines: list[BudgetLineResponse]
    total_budget: float
    created_at: Optional[datetime] = None


class MonthlyBudgetSummaryItem(BaseModel):
    category_id: int
    category_name: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_used: float


class MonthlyBudgetSummary(BaseModel):
    month: int
    year: int
    budget_id: Optional[int] = None
    items: list[MonthlyBudgetSummaryItem]
    total_budget: float
    total_spent: float
    total_remaining: float
    over_budget_count: int
