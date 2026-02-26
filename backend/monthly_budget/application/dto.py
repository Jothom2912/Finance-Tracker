"""
DTOs / Pydantic schemas for MonthlyBudget bounded context.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Request schemas ──────────────────────────────────────────────


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


# ── Response schemas ─────────────────────────────────────────────


class BudgetLineResponse(BaseModel):
    id: int
    category_id: int
    category_name: Optional[str] = None
    amount: float

    model_config = ConfigDict(from_attributes=True)


class MonthlyBudgetResponse(BaseModel):
    id: int
    month: int
    year: int
    lines: list[BudgetLineResponse]
    total_budget: float
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Summary schemas ──────────────────────────────────────────────


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
