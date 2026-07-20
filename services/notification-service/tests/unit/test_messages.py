from __future__ import annotations

from decimal import Decimal

import pytest
from app.domain.entities import NotificationType
from app.domain.messages import (
    build_bank_sync_completed,
    build_budget_line_threshold_crossed,
    build_budget_month_closed,
    build_goal_reached,
    format_amount,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0"), "0,00"),
        (Decimal("5"), "5,00"),
        (Decimal("1234.5"), "1.234,50"),
        (Decimal("1234567.89"), "1.234.567,89"),
        (Decimal("-1234.56"), "-1.234,56"),
        (Decimal("2.005"), "2,01"),  # ROUND_HALF_UP
    ],
)
def test_format_amount(value: Decimal, expected: str) -> None:
    assert format_amount(value) == expected


def test_bank_sync_no_new_transactions() -> None:
    c = build_bank_sync_completed(new_imported=0, errors=0)
    assert c.type is NotificationType.BANK_SYNC_COMPLETED
    assert "ingen nye transaktioner" in c.body


def test_bank_sync_singular_vs_plural() -> None:
    assert "1 transaktion blev" in build_bank_sync_completed(new_imported=1, errors=0).body
    assert "5 transaktioner blev" in build_bank_sync_completed(new_imported=5, errors=0).body


def test_bank_sync_reports_errors() -> None:
    body = build_bank_sync_completed(new_imported=3, errors=2).body
    assert "3 transaktioner blev importeret" in body
    assert "2 transaktioner kunne ikke behandles" in body


def test_goal_reached_with_name() -> None:
    c = build_goal_reached(goal_name="Sommerferie", target_amount=Decimal("10000"))
    assert c.type is NotificationType.GOAL_REACHED
    assert "“Sommerferie”" in c.body
    assert "10.000,00 kr" in c.body


def test_goal_reached_without_name() -> None:
    c = build_goal_reached(goal_name=None, target_amount=Decimal("500"))
    assert "sparemål" in c.body
    assert "500,00 kr" in c.body


def test_budget_month_closed_with_surplus() -> None:
    c = build_budget_month_closed(year=2026, month=6, surplus_amount=Decimal("1500.50"))
    assert c.type is NotificationType.BUDGET_MONTH_CLOSED
    assert "juni 2026" in c.body
    assert "overskud på 1.500,50 kr" in c.body


def test_budget_month_closed_zero_surplus() -> None:
    c = build_budget_month_closed(year=2026, month=12, surplus_amount=Decimal("0"))
    assert "december 2026" in c.body
    assert "intet overskud" in c.body


def test_budget_threshold_80_is_a_warning() -> None:
    c = build_budget_line_threshold_crossed(
        category_name="Dagligvarer", percentage_used=85, threshold=80, days_remaining=12
    )
    assert c.type is NotificationType.BUDGET_THRESHOLD_CROSSED
    assert c.title == "Budget-advarsel"
    assert c.body == "85% af Dagligvarer brugt, 12 dage tilbage."


def test_budget_threshold_100_is_overspend() -> None:
    c = build_budget_line_threshold_crossed(
        category_name="Transport", percentage_used=120, threshold=100, days_remaining=3
    )
    assert c.title == "Budget overskredet"
    assert c.body == "120% af Transport brugt, 3 dage tilbage."


def test_budget_threshold_singular_day() -> None:
    c = build_budget_line_threshold_crossed(
        category_name="Mad", percentage_used=80, threshold=80, days_remaining=1
    )
    assert "1 dag tilbage" in c.body


def test_budget_threshold_zero_days() -> None:
    c = build_budget_line_threshold_crossed(
        category_name="Mad", percentage_used=80, threshold=80, days_remaining=0
    )
    assert "ingen dage tilbage" in c.body
