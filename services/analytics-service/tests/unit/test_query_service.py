"""Kant-logik i AnalyticsQueryService: dato-defaults, validering,
budget_start_day-opløsning og cashflow-vinduer — mod en fake port."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import pytest
from app.application.dto import FinancialOverviewDTO, TransactionSearchResultDTO
from app.application.query_service import AnalyticsQueryService
from app.domain.exceptions import InvalidPeriodError


class FakeQueryPort:
    def __init__(self, budget_start_day: Optional[int] = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._budget_start_day = budget_start_day

    async def financial_overview(self, **kwargs: Any) -> FinancialOverviewDTO:
        self.calls.append(("financial_overview", kwargs))
        return FinancialOverviewDTO(
            start_date=kwargs["start_date"],
            end_date=kwargs["end_date"],
            total_income=0,
            total_expenses=0,
            net_change_in_period=0,
            expenses_by_category=[],
        )

    async def expenses_by_month(self, **kwargs: Any) -> list[Any]:
        self.calls.append(("expenses_by_month", kwargs))
        return []

    async def cashflow_by_month(self, **kwargs: Any) -> list[Any]:
        self.calls.append(("cashflow_by_month", kwargs))
        return []

    async def month_comparison(self, **kwargs: Any) -> Any:
        self.calls.append(("month_comparison", kwargs))
        return None

    async def search_transactions(self, **kwargs: Any) -> TransactionSearchResultDTO:
        self.calls.append(("search_transactions", kwargs))
        return TransactionSearchResultDTO(total_count=0, items=[])

    async def top_merchants(self, **kwargs: Any) -> list[Any]:
        self.calls.append(("top_merchants", kwargs))
        return []

    async def get_budget_start_day(self, **kwargs: Any) -> Optional[int]:
        self.calls.append(("get_budget_start_day", kwargs))
        return self._budget_start_day


TODAY = date(2026, 7, 6)


def make_service(port: FakeQueryPort | None = None) -> tuple[AnalyticsQueryService, FakeQueryPort]:
    port = port or FakeQueryPort()
    return AnalyticsQueryService(port, clock=lambda: TODAY), port


class TestFinancialOverviewDefaults:
    async def test_defaults_to_last_30_days(self) -> None:
        service, port = make_service()
        await service.financial_overview(user_id=7, account_id=1)

        _, kwargs = port.calls[0]
        assert kwargs["end_date"] == TODAY
        assert kwargs["start_date"] == date(2026, 6, 6)

    async def test_rejects_start_after_end(self) -> None:
        service, _ = make_service()
        with pytest.raises(InvalidPeriodError):
            await service.financial_overview(
                user_id=7,
                account_id=1,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 6, 1),
            )


class TestExpensesByMonthDefaults:
    async def test_default_window_is_one_year_back_from_the_first(self) -> None:
        service, port = make_service()
        await service.expenses_by_month(user_id=7, account_id=1, budget_start_day=1)

        _, kwargs = port.calls[-1]
        assert kwargs["start_date"] == date(2025, 7, 1)
        assert kwargs["end_date"] == TODAY

    async def test_explicit_budget_start_day_skips_port_lookup(self) -> None:
        service, port = make_service()
        await service.expenses_by_month(user_id=7, account_id=1, budget_start_day=15)

        assert all(name != "get_budget_start_day" for name, _ in port.calls)
        assert port.calls[-1][1]["budget_start_day"] == 15

    async def test_missing_budget_start_day_resolved_from_accounts_projection(self) -> None:
        service, port = make_service(FakeQueryPort(budget_start_day=20))
        await service.expenses_by_month(user_id=7, account_id=1)

        assert port.calls[0] == ("get_budget_start_day", {"user_id": 7, "account_id": 1})
        assert port.calls[-1][1]["budget_start_day"] == 20

    async def test_unknown_account_falls_back_to_day_1(self) -> None:
        service, port = make_service(FakeQueryPort(budget_start_day=None))
        await service.expenses_by_month(user_id=7, account_id=1)

        assert port.calls[-1][1]["budget_start_day"] == 1


class TestCashflowWindow:
    async def test_window_ends_at_current_budget_month_end(self) -> None:
        service, port = make_service()
        await service.cashflow_by_month(user_id=7, account_id=1, months=3, budget_start_day=1)

        _, kwargs = port.calls[-1]
        assert kwargs["start_date"] == date(2026, 5, 1)
        assert kwargs["end_date"] == date(2026, 7, 31)

    async def test_window_respects_budget_start_day(self) -> None:
        service, port = make_service()
        await service.cashflow_by_month(user_id=7, account_id=1, months=3, budget_start_day=15)

        # 2026-07-06 med start_day 15 ligger i budgetmåned juli
        # (14/6–14/7); tre måneder tilbage starter 15/4.
        _, kwargs = port.calls[-1]
        assert kwargs["start_date"] == date(2026, 4, 15)
        assert kwargs["end_date"] == date(2026, 7, 14)

    async def test_rejects_zero_months(self) -> None:
        service, _ = make_service()
        with pytest.raises(InvalidPeriodError):
            await service.cashflow_by_month(user_id=7, account_id=1, months=0)


class TestMonthComparisonValidation:
    async def test_rejects_month_out_of_range(self) -> None:
        service, _ = make_service()
        with pytest.raises(InvalidPeriodError):
            await service.month_comparison(user_id=7, account_id=1, year=2026, month=13)


class TestSearchValidation:
    async def test_rejects_inverted_range(self) -> None:
        service, _ = make_service()
        with pytest.raises(InvalidPeriodError):
            await service.search_transactions(
                user_id=7,
                account_id=1,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 6, 1),
            )
