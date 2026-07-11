from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import pytest
from app.adapters.outbound.dual_read_analytics import (
    DualReadFinancialAnalyticsRepository,
    diff_monthly,
    diff_overviews,
    diff_transactions,
)
from app.application.dto import (
    CategoryExpense,
    FinancialOverview,
    MonthlyExpenses,
    SubcategoryExpense,
    TransactionProjection,
)


def make_overview(**overrides) -> FinancialOverview:
    defaults = dict(
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        total_income=1000.0,
        total_expenses=375.0,
        net_change_in_period=625.0,
        expenses_by_category=[
            CategoryExpense(
                category_id=10,
                category_name="Mad & drikke",
                amount=325.0,
                subcategories=[
                    SubcategoryExpense(subcategory_id=101, subcategory_name="Dagligvarer", amount=200.0),
                ],
            ),
            CategoryExpense(category_id=None, category_name="Ukategoriseret", amount=50.0),
        ],
        current_account_balance=625.0,
        average_monthly_expenses=375.0,
    )
    defaults.update(overrides)
    return FinancialOverview(**defaults)


def make_tx(tx_id: int) -> TransactionProjection:
    return TransactionProjection(
        id=tx_id,
        amount=100.0,
        description="Netto",
        date=date(2026, 6, 2),
        type="expense",
        category_id=10,
        account_id=1,
    )


class StubPort:
    def __init__(
        self,
        overview: Optional[FinancialOverview] = None,
        monthly: Optional[list[MonthlyExpenses]] = None,
        transactions: Optional[list[TransactionProjection]] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self._overview = overview or make_overview()
        self._monthly = monthly if monthly is not None else [MonthlyExpenses(month="2026-06", total_expenses=375.0)]
        self._transactions = transactions if transactions is not None else [make_tx(1)]
        self._error = error

    def _maybe_raise(self) -> None:
        if self._error:
            raise self._error

    def get_financial_overview(self, account_id, start_date=None, end_date=None):
        self._maybe_raise()
        return self._overview

    def get_expenses_by_month(self, account_id, start_date=None, end_date=None, budget_start_day=1):
        self._maybe_raise()
        return self._monthly

    def list_transactions(self, account_id, start_date=None, end_date=None, category_id=None, tx_type=None, limit=100):
        self._maybe_raise()
        return self._transactions


class TestDiffHelpers:
    def test_identical_overviews_have_no_diffs(self) -> None:
        assert diff_overviews(make_overview(), make_overview()) == []

    def test_float_wobble_within_tolerance_is_ignored(self) -> None:
        assert diff_overviews(make_overview(), make_overview(total_expenses=375.005)) == []

    def test_numeric_divergence_is_reported_with_field_path(self) -> None:
        diffs = diff_overviews(make_overview(), make_overview(total_expenses=380.0))
        assert any("total_expenses" in d for d in diffs)

    def test_category_amount_divergence_is_reported(self) -> None:
        shadow = make_overview(
            expenses_by_category=[
                CategoryExpense(category_id=10, category_name="Mad & drikke", amount=999.0),
                CategoryExpense(category_id=None, category_name="Ukategoriseret", amount=50.0),
            ]
        )
        diffs = diff_overviews(make_overview(), shadow)
        assert any("expenses_by_category" in d for d in diffs)

    def test_monthly_diff_reports_missing_month(self) -> None:
        diffs = diff_monthly(
            [MonthlyExpenses(month="2026-06", total_expenses=375.0)],
            [],
        )
        assert diffs == ["month[2026-06]: 375.0 != None"]

    def test_transaction_id_set_divergence_below_limit(self) -> None:
        diffs = diff_transactions([make_tx(1), make_tx(2)], [make_tx(1)], limit=100)
        assert any("kun_legacy=[2]" in d for d in diffs)

    def test_transaction_divergence_at_limit_marked_as_truncation(self) -> None:
        diffs = diff_transactions([make_tx(1)], [make_tx(2)], limit=1)
        assert any("limit-trunkeret" in d for d in diffs)


class TestDualReadRepository:
    def test_agreement_returns_primary_without_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        repo = DualReadFinancialAnalyticsRepository(primary=StubPort(), shadow=StubPort())
        with caplog.at_level(logging.WARNING):
            result = repo.get_financial_overview(1)
        assert result == make_overview()
        assert not caplog.records

    def test_divergence_logs_warning_and_returns_primary(self, caplog: pytest.LogCaptureFixture) -> None:
        shadow = StubPort(overview=make_overview(total_expenses=999.0))
        repo = DualReadFinancialAnalyticsRepository(primary=StubPort(), shadow=shadow)
        with caplog.at_level(logging.WARNING):
            result = repo.get_financial_overview(1)
        assert result.total_expenses == 375.0
        assert any("analytics.dual_read.divergence" in r.message for r in caplog.records)

    def test_shadow_error_never_propagates(self, caplog: pytest.LogCaptureFixture) -> None:
        shadow = StubPort(error=RuntimeError("analytics nede"))
        repo = DualReadFinancialAnalyticsRepository(primary=StubPort(), shadow=shadow)
        with caplog.at_level(logging.WARNING):
            result = repo.get_expenses_by_month(1)
        assert result == [MonthlyExpenses(month="2026-06", total_expenses=375.0)]
        assert any("shadow_error" in r.message for r in caplog.records)

    def test_transactions_divergence_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        repo = DualReadFinancialAnalyticsRepository(
            primary=StubPort(transactions=[make_tx(1), make_tx(2)]),
            shadow=StubPort(transactions=[make_tx(1)]),
        )
        with caplog.at_level(logging.WARNING):
            result = repo.list_transactions(1)
        assert [t.id for t in result] == [1, 2]
        assert any("analytics.dual_read.divergence" in r.message for r in caplog.records)
