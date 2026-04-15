"""
Unit tests for the budget period calculator.

Covers:
- Standard calendar month (start_day=1)
- Custom start day (start_day=28, the real use case)
- January year-boundary wrap
- December year-boundary wrap
- Clamping of out-of-range start_day values
- determine_budget_month reverse mapping
- Round-trip consistency: budget_period and determine_budget_month agree
"""

from datetime import date, timedelta

import pytest

from backend.shared.budget_period import (
    MAX_START_DAY,
    budget_period,
    determine_budget_month,
)


# ──────────────────────────────────────────────────────────────
# budget_period: start_day=1 (calendar month, backwards compat)
# ──────────────────────────────────────────────────────────────


class TestBudgetPeriodCalendarMonth:
    def test_april_calendar_month(self) -> None:
        start, end = budget_period(2026, 4, 1)

        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 30)

    def test_february_non_leap(self) -> None:
        start, end = budget_period(2026, 2, 1)

        assert start == date(2026, 2, 1)
        assert end == date(2026, 2, 28)

    def test_february_leap_year(self) -> None:
        start, end = budget_period(2028, 2, 1)

        assert start == date(2028, 2, 1)
        assert end == date(2028, 2, 29)

    def test_january_calendar_month(self) -> None:
        start, end = budget_period(2026, 1, 1)

        assert start == date(2026, 1, 1)
        assert end == date(2026, 1, 31)

    def test_december_calendar_month(self) -> None:
        start, end = budget_period(2026, 12, 1)

        assert start == date(2026, 12, 1)
        assert end == date(2026, 12, 31)


# ──────────────────────────────────────────────────────────────
# budget_period: start_day=28 (the real use case)
# ──────────────────────────────────────────────────────────────


class TestBudgetPeriodDay28:
    def test_april_starts_in_march(self) -> None:
        """April budget with start_day=28 covers Mar 28 - Apr 27."""
        start, end = budget_period(2026, 4, 28)

        assert start == date(2026, 3, 28)
        assert end == date(2026, 4, 27)

    def test_march_starts_in_february(self) -> None:
        """March budget covers Feb 28 - Mar 27."""
        start, end = budget_period(2026, 3, 28)

        assert start == date(2026, 2, 28)
        assert end == date(2026, 3, 27)

    def test_period_length_is_consistent(self) -> None:
        """Each budget period should cover ~28-31 days."""
        for month in range(1, 13):
            start, end = budget_period(2026, month, 28)
            days = (end - start).days + 1
            assert 28 <= days <= 31, f"Month {month}: {days} days"


# ──────────────────────────────────────────────────────────────
# budget_period: year boundary (the month=1 edge case)
# ──────────────────────────────────────────────────────────────


class TestBudgetPeriodYearBoundary:
    def test_january_wraps_to_previous_year(self) -> None:
        """January budget with start_day=28 starts in December of previous year."""
        start, end = budget_period(2026, 1, 28)

        assert start == date(2025, 12, 28)
        assert end == date(2026, 1, 27)

    def test_december_stays_in_same_year(self) -> None:
        """December budget starts in November of the same year."""
        start, end = budget_period(2026, 12, 28)

        assert start == date(2026, 11, 28)
        assert end == date(2026, 12, 27)


# ──────────────────────────────────────────────────────────────
# budget_period: other start days
# ──────────────────────────────────────────────────────────────


class TestBudgetPeriodOtherStartDays:
    def test_start_day_15(self) -> None:
        """Mid-month: April = Mar 15 - Apr 14."""
        start, end = budget_period(2026, 4, 15)

        assert start == date(2026, 3, 15)
        assert end == date(2026, 4, 14)

    def test_start_day_2(self) -> None:
        """Minimal offset: April = Mar 2 - Apr 1."""
        start, end = budget_period(2026, 4, 2)

        assert start == date(2026, 3, 2)
        assert end == date(2026, 4, 1)


# ──────────────────────────────────────────────────────────────
# Clamping: out-of-range start_day values
# ──────────────────────────────────────────────────────────────


class TestBudgetPeriodClamping:
    def test_start_day_0_clamped_to_1(self) -> None:
        start, end = budget_period(2026, 4, 0)

        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 30)

    def test_negative_clamped_to_1(self) -> None:
        start, end = budget_period(2026, 4, -5)

        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 30)

    def test_start_day_29_clamped_to_28(self) -> None:
        start, end = budget_period(2026, 4, 29)

        assert start == date(2026, 3, 28)
        assert end == date(2026, 4, 27)

    def test_start_day_31_clamped_to_28(self) -> None:
        start, end = budget_period(2026, 4, 31)

        assert start == date(2026, 3, 28)
        assert end == date(2026, 4, 27)


# ──────────────────────────────────────────────────────────────
# determine_budget_month: start_day=1 (calendar)
# ──────────────────────────────────────────────────────────────


class TestDetermineBudgetMonthCalendar:
    def test_mid_month(self) -> None:
        assert determine_budget_month(date(2026, 4, 15), 1) == (2026, 4)

    def test_first_day(self) -> None:
        assert determine_budget_month(date(2026, 4, 1), 1) == (2026, 4)

    def test_last_day(self) -> None:
        assert determine_budget_month(date(2026, 4, 30), 1) == (2026, 4)


# ──────────────────────────────────────────────────────────────
# determine_budget_month: start_day=28
# ──────────────────────────────────────────────────────────────


class TestDetermineBudgetMonthDay28:
    def test_day_27_belongs_to_current_month(self) -> None:
        """Apr 27 is the last day of the April budget period."""
        assert determine_budget_month(date(2026, 4, 27), 28) == (2026, 4)

    def test_day_28_belongs_to_next_month(self) -> None:
        """Apr 28 is the first day of the May budget period."""
        assert determine_budget_month(date(2026, 4, 28), 28) == (2026, 5)

    def test_day_1_belongs_to_current_month(self) -> None:
        """Apr 1 falls within the April budget period (Mar 28 - Apr 27)."""
        assert determine_budget_month(date(2026, 4, 1), 28) == (2026, 4)

    def test_december_28_wraps_to_january_next_year(self) -> None:
        """Dec 28 belongs to January of the next year."""
        assert determine_budget_month(date(2026, 12, 28), 28) == (2027, 1)

    def test_december_27_stays_in_december(self) -> None:
        assert determine_budget_month(date(2026, 12, 27), 28) == (2026, 12)

    def test_january_1_belongs_to_january(self) -> None:
        assert determine_budget_month(date(2026, 1, 1), 28) == (2026, 1)


# ──────────────────────────────────────────────────────────────
# Round-trip: budget_period and determine_budget_month agree
# ──────────────────────────────────────────────────────────────


class TestRoundTrip:
    @pytest.mark.parametrize("start_day", [1, 10, 15, 25, 28])
    def test_all_days_in_period_map_back(self, start_day: int) -> None:
        """Every date within a budget period should map back to that month."""
        for month in range(1, 13):
            year = 2026
            period_start, period_end = budget_period(year, month, start_day)

            current = period_start
            while current <= period_end:
                result_year, result_month = determine_budget_month(current, start_day)
                assert (result_year, result_month) == (year, month), (
                    f"start_day={start_day}, budget month={year}-{month:02d}, "
                    f"date={current} mapped to {result_year}-{result_month:02d}"
                )
                current += timedelta(days=1)

    def test_adjacent_periods_dont_overlap(self) -> None:
        """The end of one period is the day before the start of the next."""
        for month in range(1, 12):
            _, end = budget_period(2026, month, 28)
            next_start, _ = budget_period(2026, month + 1, 28)

            assert next_start - end == timedelta(days=1), (
                f"Gap between month {month} and {month + 1}: "
                f"end={end}, next_start={next_start}"
            )

    @pytest.mark.parametrize("start_day", [1, 15, 28])
    def test_leap_year_round_trip(self, start_day: int) -> None:
        """366 days in a leap year all map back correctly."""
        for month in range(1, 13):
            year = 2028
            period_start, period_end = budget_period(year, month, start_day)

            current = period_start
            while current <= period_end:
                result_year, result_month = determine_budget_month(current, start_day)
                assert (result_year, result_month) == (year, month), (
                    f"Leap year: start_day={start_day}, budget month={year}-{month:02d}, "
                    f"date={current} mapped to {result_year}-{result_month:02d}"
                )
                current += timedelta(days=1)

    def test_adjacent_periods_year_boundary(self) -> None:
        """December -> January transition has no gap."""
        _, dec_end = budget_period(2026, 12, 28)
        jan_start, _ = budget_period(2027, 1, 28)

        assert jan_start - dec_end == timedelta(days=1)
