from __future__ import annotations

from datetime import date

import pytest
from app.domain.budget_period import (
    budget_period,
    determine_budget_month,
    histogram_bucket_to_budget_month,
)


class TestBudgetPeriod:
    def test_start_day_1_is_calendar_month(self) -> None:
        assert budget_period(2026, 2, 1) == (date(2026, 2, 1), date(2026, 2, 28))

    def test_start_day_1_leap_year_february(self) -> None:
        assert budget_period(2028, 2, 1) == (date(2028, 2, 1), date(2028, 2, 29))

    def test_start_day_15_spans_two_calendar_months(self) -> None:
        assert budget_period(2026, 3, 15) == (date(2026, 2, 15), date(2026, 3, 14))

    def test_january_period_starts_in_previous_year(self) -> None:
        assert budget_period(2026, 1, 15) == (date(2025, 12, 15), date(2026, 1, 14))

    def test_start_day_clamped_to_28(self) -> None:
        assert budget_period(2026, 3, 31) == budget_period(2026, 3, 28)


class TestDetermineBudgetMonth:
    def test_start_day_1_is_identity(self) -> None:
        assert determine_budget_month(date(2026, 7, 31), 1) == (2026, 7)

    def test_on_or_after_start_day_rolls_to_next_month(self) -> None:
        assert determine_budget_month(date(2026, 7, 15), 15) == (2026, 8)
        assert determine_budget_month(date(2026, 7, 14), 15) == (2026, 7)

    def test_december_rolls_to_next_year(self) -> None:
        assert determine_budget_month(date(2026, 12, 20), 15) == (2027, 1)


class TestHistogramBucketToBudgetMonth:
    """En date_histogram-bucket med offset +(start_day-1)d starter altid
    på dag start_day — labelen skal matche determine_budget_month for
    enhver transaktion inde i bucketen."""

    def test_start_day_1_identity(self) -> None:
        assert histogram_bucket_to_budget_month(date(2026, 7, 1), 1) == "2026-07"

    @pytest.mark.parametrize("start_day", [15, 28])
    def test_bucket_start_labels_next_month(self, start_day: int) -> None:
        bucket_start = date(2026, 7, start_day)
        assert histogram_bucket_to_budget_month(bucket_start, start_day) == "2026-08"

    def test_december_bucket_labels_january_next_year(self) -> None:
        assert histogram_bucket_to_budget_month(date(2026, 12, 15), 15) == "2027-01"

    @pytest.mark.parametrize("start_day", [1, 15, 28])
    def test_label_agrees_with_determine_budget_month_across_bucket(self, start_day: int) -> None:
        # Alle dage i bucketen [start, næste start) skal have samme
        # budgetmåned som bucket-labelen.
        from datetime import timedelta

        bucket_start = date(2026, 5, start_day)
        label = histogram_bucket_to_budget_month(bucket_start, start_day)
        day = bucket_start
        while True:
            year, month = determine_budget_month(day, start_day)
            assert f"{year}-{month:02d}" == label, f"dag {day} faldt udenfor {label}"
            day += timedelta(days=1)
            next_start = date(2026, 6, start_day) if start_day != 1 else date(2026, 6, 1)
            if day >= next_start:
                break
