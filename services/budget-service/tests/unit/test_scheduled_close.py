"""Unit tests for the day-7 due-rule (F1-07).

Ren domain-funktion med injiceret ``today`` — ingen frysning nødvendig.
"""

from __future__ import annotations

from datetime import date

import pytest
from app.domain.scheduled_close import is_due_for_scheduled_close


@pytest.mark.parametrize(
    ("year", "month", "today", "expected"),
    [
        # Dag-7-grænsen for forrige måned
        (2026, 6, date(2026, 7, 6), False),
        (2026, 6, date(2026, 7, 7), True),
        (2026, 6, date(2026, 7, 8), True),
        # Indeværende måned er aldrig due
        (2026, 7, date(2026, 7, 31), False),
        # Ældre måneder er overdue — due uanset dag
        (2026, 3, date(2026, 7, 1), True),
        (2025, 11, date(2026, 7, 1), True),
        # December→januar-rollover
        (2025, 12, date(2026, 1, 6), False),
        (2025, 12, date(2026, 1, 7), True),
        # Fremtidig måned (data-fejl) er ikke due
        (2026, 9, date(2026, 7, 17), False),
    ],
)
def test_is_due_for_scheduled_close(year: int, month: int, today: date, expected: bool) -> None:
    assert is_due_for_scheduled_close(year, month, today) is expected


def test_close_day_is_configurable() -> None:
    assert is_due_for_scheduled_close(2026, 6, date(2026, 7, 3), close_day=3) is True
    assert is_due_for_scheduled_close(2026, 6, date(2026, 7, 2), close_day=3) is False
