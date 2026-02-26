"""Unit tests for MonthlyBudgetService business logic."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from backend.monthly_budget.application.dto import BudgetLineCreate, MonthlyBudgetUpdate
from backend.monthly_budget.application.ports.outbound import (
    ICategoryPort,
    IMonthlyBudgetRepository,
    ITransactionPort,
)
from backend.monthly_budget.application.service import MonthlyBudgetService
from backend.monthly_budget.domain.entities import BudgetLine, MonthlyBudget
from backend.monthly_budget.domain.exceptions import MonthlyBudgetNotFound


@pytest.fixture
def mock_budget_repo() -> Mock:
    return Mock(spec=IMonthlyBudgetRepository)


@pytest.fixture
def mock_tx_port() -> Mock:
    return Mock(spec=ITransactionPort)


@pytest.fixture
def mock_category_port() -> Mock:
    mock = Mock(spec=ICategoryPort)
    mock.get_all_names.return_value = {}
    return mock


@pytest.fixture
def service(
    mock_budget_repo: Mock,
    mock_tx_port: Mock,
    mock_category_port: Mock,
) -> MonthlyBudgetService:
    return MonthlyBudgetService(
        budget_repo=mock_budget_repo,
        transaction_port=mock_tx_port,
        category_port=mock_category_port,
    )


def _sample_budget(account_id: int = 1) -> MonthlyBudget:
    return MonthlyBudget(
        id=7,
        month=2,
        year=2026,
        account_id=account_id,
        lines=[BudgetLine(id=1, category_id=9, amount=2000.0)],
    )


def test_update_validates_budget_ownership(
    service: MonthlyBudgetService,
    mock_budget_repo: Mock,
    mock_category_port: Mock,
) -> None:
    existing = _sample_budget(account_id=12)
    updated = _sample_budget(account_id=12)
    updated.lines = [BudgetLine(id=1, category_id=11, amount=1500.0)]

    mock_budget_repo.get_by_id_for_account.return_value = existing
    mock_budget_repo.update.return_value = updated
    mock_category_port.exists.return_value = True

    dto = MonthlyBudgetUpdate(lines=[BudgetLineCreate(category_id=11, amount=1500.0)])
    result = service.update(budget_id=7, account_id=12, dto=dto)

    mock_budget_repo.get_by_id_for_account.assert_called_once_with(7, 12)
    mock_budget_repo.update.assert_called_once()
    assert result.id == 7
    assert result.lines[0].category_id == 11


def test_update_raises_not_found_when_budget_not_owned(
    service: MonthlyBudgetService,
    mock_budget_repo: Mock,
) -> None:
    mock_budget_repo.get_by_id_for_account.return_value = None

    dto = MonthlyBudgetUpdate(lines=[BudgetLineCreate(category_id=9, amount=1000.0)])
    with pytest.raises(MonthlyBudgetNotFound):
        service.update(budget_id=7, account_id=99, dto=dto)

    mock_budget_repo.get_by_id_for_account.assert_called_once_with(7, 99)


def test_delete_is_scoped_to_account(
    service: MonthlyBudgetService,
    mock_budget_repo: Mock,
) -> None:
    mock_budget_repo.delete.return_value = True

    result = service.delete(budget_id=7, account_id=12)

    assert result is True
    mock_budget_repo.delete.assert_called_once_with(7, 12)


def test_summary_counts_unbudgeted_spending_as_over_budget(
    service: MonthlyBudgetService,
    mock_budget_repo: Mock,
    mock_tx_port: Mock,
    mock_category_port: Mock,
) -> None:
    # Budgeted category 9 has spend below budget.
    mock_budget_repo.get_by_account_and_period.return_value = MonthlyBudget(
        id=1,
        month=2,
        year=2026,
        account_id=1,
        lines=[BudgetLine(id=1, category_id=9, amount=1000.0)],
    )
    # Category 11 has spending but no budget line.
    mock_tx_port.get_expenses_by_category.return_value = {9: 500.0, 11: 300.0}
    mock_category_port.get_all_names.return_value = {
        9: "madvarer/dagligvarer",
        11: "transport",
    }

    summary = service.get_summary(account_id=1, month=2, year=2026)

    assert summary.over_budget_count == 1
    unbudgeted = [i for i in summary.items if i.category_id == 11][0]
    assert unbudgeted.budget_amount == 0.0
    assert unbudgeted.remaining_amount == -300.0
