"""Due-rule for scheduled month-close (F1-07, ADR-0003's day-7 trigger).

A budget month is due for automatic close from day ``close_day`` in the
FOLLOWING month — bank transactions can lag 1-3 days, so closing on the 1st
would snapshot incomplete numbers. Months further in the past are overdue
and due immediately.

Pure function; the caller injects ``today`` (no wall-clock reads here).
"""

from __future__ import annotations

from datetime import date

DEFAULT_CLOSE_DAY = 7


def is_due_for_scheduled_close(year: int, month: int, today: date, close_day: int = DEFAULT_CLOSE_DAY) -> bool:
    if month == 12:
        earliest_close = date(year + 1, 1, close_day)
    else:
        earliest_close = date(year, month + 1, close_day)
    return today >= earliest_close
