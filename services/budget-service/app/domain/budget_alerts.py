"""Pure threshold-crossing evaluation for mid-month budget alerts (F2-03).

Given a monthly budget's lines and the spent-per-category map, decide which
(line, threshold) pairs are at or over their share of the budget. One crossing
per threshold, so a line at >=100% yields both the 80 and the 100 crossing.

No I/O, no wall-clock: the caller supplies spent amounts and thresholds. The
alert scheduler keeps NO state — uniqueness ("notify once per line/threshold/
period") is enforced downstream by notification-service's unique source_key, so
this may be called every tick and re-emit the same crossings idempotently.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import BudgetLine


@dataclass(frozen=True)
class LineCrossing:
    category_id: int
    budget_amount: float
    spent_amount: float
    percentage_used: int
    threshold: int


def evaluate_line_crossings(
    lines: list[BudgetLine],
    spent_by_category: dict[int, float],
    thresholds: list[int],
) -> list[LineCrossing]:
    """Return one LineCrossing per (line, threshold) that is at or over threshold.

    Lines with a non-positive budget are skipped (no division, no alert). A
    category absent from ``spent_by_category`` counts as 0 spent (no crossing).
    Percentage is floored to an int; results are ordered by (category_id,
    threshold) for deterministic output.
    """
    crossings: list[LineCrossing] = []
    ordered_thresholds = sorted(set(thresholds))

    for line in sorted(lines, key=lambda item: item.category_id):
        if line.amount <= 0:
            continue

        spent = spent_by_category.get(line.category_id, 0.0)
        percentage = int(spent / line.amount * 100)

        for threshold in ordered_thresholds:
            if percentage >= threshold:
                crossings.append(
                    LineCrossing(
                        category_id=line.category_id,
                        budget_amount=line.amount,
                        spent_amount=spent,
                        percentage_used=percentage,
                        threshold=threshold,
                    )
                )

    return crossings
