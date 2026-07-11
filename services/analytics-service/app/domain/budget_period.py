"""Budgetperiode-logik (kopi af gateway-servicens app/shared/budget_period.py).

Bevidst duplikeret: repoet har ingen delt app-kode-pakke ud over
contracts/auth, og kontrakten er lille, stabil og unit-testet begge
steder. ``histogram_bucket_to_budget_month`` er analytics-specifik og
oversætter ES date_histogram-buckets (calendar_interval=month med
offset ``+(start_day-1)d``) til budgetmåneds-labels.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

MIN_START_DAY = 1
MAX_START_DAY = 28


def budget_period(year: int, month: int, start_day: int) -> tuple[date, date]:
    start_day = _clamp_start_day(start_day)

    if start_day == 1:
        _, last = monthrange(year, month)
        return date(year, month, 1), date(year, month, last)

    prev_year, prev_month = _prev_month(year, month)
    start_date = date(prev_year, prev_month, start_day)
    end_date = date(year, month, start_day - 1)

    return start_date, end_date


def determine_budget_month(tx_date: date, start_day: int) -> tuple[int, int]:
    start_day = _clamp_start_day(start_day)

    if start_day == 1:
        return tx_date.year, tx_date.month

    if tx_date.day >= start_day:
        return _next_month(tx_date.year, tx_date.month)

    return tx_date.year, tx_date.month


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


def _clamp_start_day(start_day: int) -> int:
    return max(MIN_START_DAY, min(MAX_START_DAY, start_day))


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1
