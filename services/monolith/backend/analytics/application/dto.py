"""DTOs for Analytics bounded context."""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict


class ExpensesByCategory(BaseModel):
    category_name: str
    amount: float


class FinancialOverview(BaseModel):
    start_date: date
    end_date: date
    total_income: float
    total_expenses: float
    net_change_in_period: float
    expenses_by_category: Dict[str, float]
    current_account_balance: Optional[float] = None
    average_monthly_expenses: Optional[float] = None


class TransactionProjection(BaseModel):
    """Read-only projection of a transaction materialised in the
    monolith MySQL table by ``TransactionSyncConsumer``.

    Used by the GraphQL read gateway.  Since transactions are owned
    by ``transaction-service`` this DTO purposely has no write side.
    """

    id: int
    amount: float
    description: Optional[str]
    date: date
    type: str
    category_id: Optional[int]
    account_id: int
    categorization_tier: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
