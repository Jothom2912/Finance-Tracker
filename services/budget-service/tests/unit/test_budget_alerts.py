"""Unit tests for mid-month budget alert threshold-crossing evaluation (F2-03).

Pure domain — no I/O, no clock. Spent amounts are injected.
"""

from __future__ import annotations

from app.domain.budget_alerts import LineCrossing, evaluate_line_crossings
from app.domain.entities import BudgetLine


def _line(category_id: int, amount: float) -> BudgetLine:
    return BudgetLine(id=None, category_id=category_id, amount=amount)


class TestEvaluateLineCrossings:
    def test_below_lowest_threshold_yields_nothing(self) -> None:
        lines = [_line(3, 1000.0)]
        assert evaluate_line_crossings(lines, {3: 799.0}, [80, 100]) == []

    def test_at_threshold_fires(self) -> None:
        crossings = evaluate_line_crossings([_line(3, 1000.0)], {3: 800.0}, [80, 100])
        assert crossings == [
            LineCrossing(
                category_id=3,
                budget_amount=1000.0,
                spent_amount=800.0,
                percentage_used=80,
                threshold=80,
            )
        ]

    def test_above_80_below_100_fires_only_80(self) -> None:
        crossings = evaluate_line_crossings([_line(3, 1000.0)], {3: 850.0}, [80, 100])
        assert [c.threshold for c in crossings] == [80]
        assert crossings[0].percentage_used == 85

    def test_over_budget_fires_both_thresholds(self) -> None:
        crossings = evaluate_line_crossings([_line(3, 1000.0)], {3: 1200.0}, [80, 100])
        assert [c.threshold for c in crossings] == [80, 100]
        assert all(c.percentage_used == 120 for c in crossings)

    def test_exactly_100_fires_both(self) -> None:
        crossings = evaluate_line_crossings([_line(3, 1000.0)], {3: 1000.0}, [80, 100])
        assert [c.threshold for c in crossings] == [80, 100]

    def test_zero_budget_line_is_skipped(self) -> None:
        # No division by zero, no alert on an unbudgeted (0) line.
        assert evaluate_line_crossings([_line(3, 0.0)], {3: 500.0}, [80, 100]) == []

    def test_missing_category_counts_as_zero_spent(self) -> None:
        assert evaluate_line_crossings([_line(3, 1000.0)], {}, [80, 100]) == []

    def test_multiple_lines_are_evaluated_independently(self) -> None:
        lines = [_line(3, 1000.0), _line(5, 200.0)]
        spent = {3: 100.0, 5: 180.0}  # 10% and 90%
        crossings = evaluate_line_crossings(lines, spent, [80, 100])
        assert [(c.category_id, c.threshold) for c in crossings] == [(5, 80)]

    def test_output_ordered_by_category_then_threshold(self) -> None:
        lines = [_line(9, 100.0), _line(2, 100.0)]
        spent = {9: 100.0, 2: 100.0}
        crossings = evaluate_line_crossings(lines, spent, [100, 80])
        assert [(c.category_id, c.threshold) for c in crossings] == [
            (2, 80),
            (2, 100),
            (9, 80),
            (9, 100),
        ]

    def test_duplicate_thresholds_deduped(self) -> None:
        crossings = evaluate_line_crossings([_line(3, 100.0)], {3: 90.0}, [80, 80])
        assert [c.threshold for c in crossings] == [80]
