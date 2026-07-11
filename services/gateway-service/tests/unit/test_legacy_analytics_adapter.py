"""Regression-lås: legacy-adapteren skal give identisk output med den
direkte AnalyticsService-brug (nul adfærdsændring ved port-skiftet)."""

from __future__ import annotations

from datetime import date

from app.adapters.outbound.legacy_analytics_adapter import LegacyFinancialAnalyticsAdapter
from app.application.service import AnalyticsService
from tests.unit.test_analytics_service import (
    FakeAnalyticsReadRepository,
    FakeCategoryReadRepository,
)


def make_adapter() -> tuple[LegacyFinancialAnalyticsAdapter, AnalyticsService]:
    service = AnalyticsService(FakeAnalyticsReadRepository(), category_repo=FakeCategoryReadRepository())
    return LegacyFinancialAnalyticsAdapter(service), service


JUNE = {"start_date": date(2026, 6, 1), "end_date": date(2026, 6, 30)}


def test_overview_is_identical_to_direct_service_call() -> None:
    adapter, service = make_adapter()
    assert adapter.get_financial_overview(1, **JUNE) == service.get_financial_overview(account_id=1, **JUNE)


def test_expenses_by_month_maps_dicts_to_dto() -> None:
    adapter, service = make_adapter()
    rows = service.get_expenses_by_month(account_id=1, **JUNE)
    result = adapter.get_expenses_by_month(1, **JUNE)
    assert [(m.month, m.total_expenses) for m in result] == [(r["month"], r["total_expenses"]) for r in rows]


def test_list_transactions_is_identical_to_direct_service_call() -> None:
    adapter, service = make_adapter()
    assert adapter.list_transactions(1, category_id=10, tx_type="expense") == (
        service.list_transaction_projections(account_id=1, category_id=10, tx_type="expense")
    )
