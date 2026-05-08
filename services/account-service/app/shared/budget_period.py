"""
Budget period calculator.

Pure functions to map (year, month, start_day) to a date range and back.
Used by both monthly_budget and analytics services.

start_day is capped at 1-28 because every month has at least 28 days.
Values outside this range are clamped silently.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

MIN_START_DAY = 1
MAX_START_DAY = 28


def budget_period(year: int, month: int, start_day: int) -> tuple[date, date]:
    """
    Calculate the inclusive date range for a budget month.

    When start_day == 1: standard calendar month (e.g. Apr 1 - Apr 30).
    When start_day == 28: "April" means Mar 28 - Apr 27.

    The budget month label (year, month) refers to the month that contains
    the *end* of the period. So budget "April 2026" with start_day=28
    starts in March and ends in April.

    Returns:
        (start_date, end_date) inclusive on both ends.
    """
    start_day = _clamp_start_day(start_day)

    if start_day == 1:
        _, last = monthrange(year, month)
        return date(year, month, 1), date(year, month, last)

    prev_year, prev_month = _prev_month(year, month)
    start_date = date(prev_year, prev_month, start_day)
    end_date = date(year, month, start_day - 1)

    return start_date, end_date


def determine_budget_month(tx_date: date, start_day: int) -> tuple[int, int]:
    """
    Given a transaction date, determine which budget month it belongs to.

    Returns:
        (year, month) of the budget period that contains tx_date.
    """
    start_day = _clamp_start_day(start_day)

    if start_day == 1:
        return tx_date.year, tx_date.month

    if tx_date.day >= start_day:
        return _next_month(tx_date.year, tx_date.month)

    return tx_date.year, tx_date.month


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
