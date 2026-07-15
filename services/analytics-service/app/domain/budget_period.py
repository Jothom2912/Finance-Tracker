"""Analytics-specifikke budgetperiode-udvidelser oven på finans-tracker-domain.

Kernefunktionerne (``budget_period``, ``determine_budget_month``) kommer fra
den delte pakke og re-eksporteres her, så lokale imports er uændrede.
"""

from __future__ import annotations

from datetime import date

from domain import budget_period, determine_budget_month

__all__ = [
    "budget_period",
    "determine_budget_month",
    "histogram_bucket_to_budget_month",
    "months_in_period",
]


def histogram_bucket_to_budget_month(bucket_start: date, start_day: int) -> str:
    """Label for en ES date_histogram-bucket som ``"YYYY-MM"`` budgetmåned.

    En bucket med offset ``+(start_day-1)d`` starter på dag ``start_day``,
    så dens budgetmåned er præcis ``determine_budget_month`` af startdatoen
    (identitet ved start_day=1, næste måned ellers).
    """
    year, month = determine_budget_month(bucket_start, start_day)
    return f"{year}-{month:02d}"


def months_in_period(start_date: date, end_date: date) -> float:
    """Antal måneder i perioden — replikerer gatewayens formel præcist
    (dual-read sammenligner average_monthly_expenses direkte)."""
    months: float = max(
        1,
        (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1,
    )
    if months == 1:
        days_in_period = (end_date - start_date).days + 1
        months = max(1, days_in_period / 30.0)
    return months
