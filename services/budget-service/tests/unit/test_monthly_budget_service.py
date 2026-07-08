"""Unit tests for MonthlyBudgetService.

Fokus på to sikkerhedsregressioner:
1. close_month skal fejle CLOSED når transaction-service er utilgængelig —
   måneden må IKKE lukkes og der må IKKE udsendes en outbox-event.
2. Ejerskab: alle repository-opslag skal filtrere på user_id fra JWT.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from app.application.dto import MonthlyBudgetUpdate
from app.application.monthly_budget_service import MonthlyBudgetService
from app.domain.entities import BudgetLine, MonthlyBudget
from app.domain.exceptions import (
    MonthlyBudgetNotFound,
    UpstreamServiceUnavailable,
)


@pytest.fixture
def service():
    uow = AsyncMock()
    transaction_port = AsyncMock()
    category_port = AsyncMock()
    category_port.get_all_names.return_value = {10: "Mad"}
    svc = MonthlyBudgetService(
        uow=uow,
        transaction_port=transaction_port,
        category_port=category_port,
    )
    return svc, uow, transaction_port, category_port


def make_monthly_budget(budget_id=1, month=6, year=2026, account_id=1, user_id=1):
    return MonthlyBudget(
        id=budget_id,
        month=month,
        year=year,
        account_id=account_id,
        user_id=user_id,
        lines=[BudgetLine(id=1, category_id=10, amount=1000.0)],
        created_at=datetime(2026, 6, 1),
    )


# ---------------------------------------------------------------------------
# close_month — fail-closed når transaction-service er nede
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_month_fails_closed_when_transaction_service_unavailable(service):
    svc, uow, transaction_port, _ = service
    uow.monthly_budgets.get_by_account_and_period.return_value = make_monthly_budget()
    transaction_port.get_expenses_by_category.side_effect = UpstreamServiceUnavailable("transaction-service")

    with pytest.raises(UpstreamServiceUnavailable):
        await svc.close_month(account_id=1, year=2026, month=6, user_id=1)

    uow.monthly_budgets.mark_closed.assert_not_awaited()
    uow.outbox.add.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_month_success_marks_closed_and_emits_event(service):
    svc, uow, transaction_port, _ = service
    uow.monthly_budgets.get_by_account_and_period.return_value = make_monthly_budget()
    transaction_port.get_expenses_by_category.return_value = {10: 400.0}
    uow.monthly_budgets.mark_closed.return_value = True

    await svc.close_month(account_id=1, year=2026, month=6, user_id=1)

    uow.monthly_budgets.mark_closed.assert_awaited_once_with(1)
    uow.outbox.add.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_month_raises_not_found_when_budget_belongs_to_other_user(service):
    svc, uow, _, _ = service
    # Repo filtrerer på user_id — en anden brugers budget findes ikke for user 2
    uow.monthly_budgets.get_by_account_and_period.return_value = None

    with pytest.raises(MonthlyBudgetNotFound):
        await svc.close_month(account_id=1, year=2026, month=6, user_id=2)

    uow.monthly_budgets.get_by_account_and_period.assert_awaited_once_with(1, 6, 2026, 2)
    uow.monthly_budgets.mark_closed.assert_not_awaited()
    uow.outbox.add.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_summary — read-only bevarer graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_summary_degrades_gracefully_when_transaction_service_unavailable(service):
    svc, uow, transaction_port, _ = service
    uow.monthly_budgets.get_by_account_and_period.return_value = make_monthly_budget()
    transaction_port.get_expenses_by_category.side_effect = UpstreamServiceUnavailable("transaction-service")

    summary = await svc.get_summary(account_id=1, month=6, year=2026, user_id=1)

    assert summary.total_spent == 0.0
    assert summary.total_budget == 1000.0


# ---------------------------------------------------------------------------
# Ejerskab — user_id fra JWT sendes med til repository-opslag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_none_passes_user_id_and_returns_none_for_other_user(service):
    svc, uow, _, _ = service
    uow.monthly_budgets.get_by_account_and_period.return_value = None

    result = await svc.get_or_none(account_id=1, month=6, year=2026, user_id=2)

    assert result is None
    uow.monthly_budgets.get_by_account_and_period.assert_awaited_once_with(1, 6, 2026, 2)


@pytest.mark.asyncio
async def test_update_raises_not_found_when_budget_belongs_to_other_user(service):
    svc, uow, _, _ = service
    uow.monthly_budgets.get_by_id_for_account.return_value = None

    dto = MonthlyBudgetUpdate(lines=[])
    with pytest.raises(MonthlyBudgetNotFound):
        await svc.update(budget_id=1, account_id=1, user_id=2, dto=dto)

    uow.monthly_budgets.get_by_id_for_account.assert_awaited_once_with(1, 1, 2)


@pytest.mark.asyncio
async def test_delete_passes_user_id_to_repository(service):
    svc, uow, _, _ = service
    uow.monthly_budgets.delete.return_value = False

    result = await svc.delete(budget_id=1, account_id=1, user_id=2)

    assert result is False
    uow.monthly_budgets.delete.assert_awaited_once_with(1, 1, 2)
