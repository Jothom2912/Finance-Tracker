from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SubcategoryExpense(BaseModel):
    """Expense slice for one subcategory within a category bucket.

    ``subcategory_id`` is None for the remainder that has a category but
    no subcategory ("(Ingen underkategori)" in the UI).
    """

    subcategory_id: Optional[int]
    subcategory_name: str
    amount: float


class CategoryExpense(BaseModel):
    """Expense bucket keyed by category id (None = 'Ukategoriseret').

    Aggregation is id-based; the name is display metadata, so renamed
    categories no longer collide and the frontend can filter by id.
    """

    category_id: Optional[int]
    category_name: str
    amount: float
    subcategories: list[SubcategoryExpense] = Field(default_factory=list)


class FinancialOverview(BaseModel):
    start_date: date
    end_date: date
    total_income: float
    total_expenses: float
    net_change_in_period: float
    expenses_by_category: list[CategoryExpense]
    current_account_balance: Optional[float] = None
    average_monthly_expenses: Optional[float] = None


class TransactionProjection(BaseModel):
    id: int
    amount: float
    description: Optional[str]
    date: date
    type: str
    category_id: Optional[int]
    category_name: Optional[str] = None
    subcategory_id: Optional[int] = None
    subcategory_name: Optional[str] = None
    account_id: int
    categorization_tier: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
