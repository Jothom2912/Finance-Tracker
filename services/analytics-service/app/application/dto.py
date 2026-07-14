"""Read-side DTOs.

``FinancialOverviewDTO``-familien spejler gateway-servicens
``FinancialOverview`` felt for felt — dual-read-verifikationen i
gatewayen sammenligner de to strukturer direkte, så formerne må ikke
divergere.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class SubcategoryExpenseDTO(BaseModel):
    subcategory_id: Optional[int]
    subcategory_name: str
    amount: float


class CategoryExpenseDTO(BaseModel):
    """Udgifts-bucket nøglet på category_id (None = 'Ukategoriseret')."""

    category_id: Optional[int]
    category_name: str
    amount: float
    subcategories: list[SubcategoryExpenseDTO] = Field(default_factory=list)


class FinancialOverviewDTO(BaseModel):
    start_date: date
    end_date: date
    total_income: float
    total_expenses: float
    net_change_in_period: float
    expenses_by_category: list[CategoryExpenseDTO]
    current_account_balance: Optional[float] = None
    average_monthly_expenses: Optional[float] = None


class MonthlyExpensesDTO(BaseModel):
    """Udgifter per budgetmåned; ``month`` er ``"YYYY-MM"``-label."""

    month: str
    total_expenses: float


class MonthlyCashflowDTO(BaseModel):
    month: str
    total_income: float
    total_expenses: float
    net: float


class TransactionProjectionDTO(BaseModel):
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


class TransactionSearchResultDTO(BaseModel):
    total_count: int
    items: list[TransactionProjectionDTO]


class HybridSearchResultDTO(BaseModel):
    """AI-20: RRF-fusioneret BM25+kNN-resultat.

    Ingen ``total_count`` — fusionerede ranks har ingen meningsfuld
    totalmængde. ``used_knn=False`` betyder degraderet til ren BM25
    (intet query_vector medsendt).
    """

    items: list[TransactionProjectionDTO]
    used_knn: bool


class CategoryDeltaDTO(BaseModel):
    category_id: Optional[int]
    category_name: str
    current_amount: float
    previous_amount: float
    change_amount: float
    # None når previous_amount == 0 (ny kategori) — frontend viser "Ny".
    change_percent: Optional[float] = None


class MonthComparisonDTO(BaseModel):
    month: int
    year: int
    previous_month: int
    previous_year: int
    total_current: float
    total_previous: float
    deltas: list[CategoryDeltaDTO]


class TopMerchantDTO(BaseModel):
    """Approksimation: grupperet på rå beskrivelse (intet merchant-felt i events)."""

    description: str
    total_amount: float
    transaction_count: int
