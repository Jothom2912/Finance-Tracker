from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.application.dto import BudgetCreateDTO, BudgetUpdateDTO
from app.application.service import BudgetService
from app.domain.entities import Budget
from app.domain.exceptions import (
    AccountRequiredForBudget,
    CategoryNotFoundForBudget,
    CategoryRequiredForBudget,
)


@pytest.fixture
def service():
    repo = AsyncMock()
    category_port = AsyncMock()
    return BudgetService(repo, category_port), repo, category_port


def make_budget(
    budget_id=1,
    user_id=1,
    amount=1000,
    budget_date=date(2026, 6, 1),
    account_id=1,
    category_id=10,
):
    return Budget(
        id=budget_id,
        amount=amount,
        budget_date=budget_date,
        account_id=account_id,
        category_id=category_id,
        user_id=user_id,
    )


@pytest.mark.asyncio
async def test_get_budget_returns_budget_when_user_owns_it(service):
    svc, repo, _ = service
    repo.get_by_id.return_value = make_budget()

    result = await svc.get_budget(budget_id=1, user_id=1)

    assert result is not None
    assert result.id == 1
    assert result.amount == 1000


@pytest.mark.asyncio
async def test_get_budget_returns_none_when_not_found(service):
    svc, repo, _ = service
    repo.get_by_id.return_value = None

    result = await svc.get_budget(budget_id=999, user_id=1)

    assert result is None


@pytest.mark.asyncio
async def test_get_budget_returns_none_when_user_does_not_own_it(service):
    svc, repo, _ = service
    repo.get_by_id.return_value = make_budget(user_id=2)

    result = await svc.get_budget(budget_id=1, user_id=1)

    assert result is None


@pytest.mark.asyncio
async def test_list_budgets_returns_all_budgets(service):
    svc, repo, _ = service
    repo.get_all.return_value = [
        make_budget(budget_id=1, amount=100),
        make_budget(budget_id=2, amount=200),
    ]

    result = await svc.list_budgets(account_id=1, user_id=1)

    assert len(result) == 2
    assert result[0].amount == 100
    assert result[1].amount == 200


@pytest.mark.asyncio
async def test_create_budget_success(service):
    svc, repo, category_port = service
    category_port.exists.return_value = True
    repo.create.return_value = make_budget()

    dto = BudgetCreateDTO(
        amount=1000,
        budget_date=date(2026, 6, 1),
        account_id=1,
        category_id=10,
    )

    result = await svc.create_budget(user_id=1, dto=dto)

    assert result.id == 1
    assert result.amount == 1000
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_budget_requires_account(service):
    svc, _, _ = service

    dto = BudgetCreateDTO(
        amount=1000,
        budget_date=date(2026, 6, 1),
        account_id=0,
        category_id=10,
    )

    with pytest.raises(AccountRequiredForBudget):
        await svc.create_budget(user_id=1, dto=dto)


@pytest.mark.asyncio
async def test_create_budget_requires_category(service):
    svc, _, _ = service

    dto = BudgetCreateDTO(
        amount=1000,
        budget_date=date(2026, 6, 1),
        account_id=1,
        category_id=0,
    )

    with pytest.raises(CategoryRequiredForBudget):
        await svc.create_budget(user_id=1, dto=dto)


@pytest.mark.asyncio
async def test_create_budget_raises_when_category_not_found(service):
    svc, _, category_port = service
    category_port.exists.return_value = False

    dto = BudgetCreateDTO(
        amount=1000,
        budget_date=date(2026, 6, 1),
        account_id=1,
        category_id=999,
    )

    with pytest.raises(CategoryNotFoundForBudget):
        await svc.create_budget(user_id=1, dto=dto)


@pytest.mark.asyncio
async def test_create_budget_uses_month_and_year_as_budget_date(service):
    svc, repo, category_port = service
    category_port.exists.return_value = True
    repo.create.return_value = make_budget(budget_date=date(2026, 7, 1))

    dto = BudgetCreateDTO(
        amount=1000,
        budget_date=date(2026, 6, 1),
        account_id=1,
        category_id=10,
        month=7,
        year=2026,
    )

    result = await svc.create_budget(user_id=1, dto=dto)

    assert result.budget_date == date(2026, 7, 1)


@pytest.mark.asyncio
async def test_update_budget_success(service):
    svc, repo, category_port = service

    repo.get_by_id.return_value = make_budget()
    category_port.exists.return_value = True
    repo.update.return_value = make_budget(amount=1500, category_id=20)

    dto = BudgetUpdateDTO(
        amount=1500,
        category_id=20,
    )

    result = await svc.update_budget(
        budget_id=1,
        user_id=1,
        dto=dto,
    )

    assert result is not None
    assert result.amount == 1500
    assert result.category_id == 20
    repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_budget_returns_none_when_not_found(service):
    svc, repo, _ = service
    repo.get_by_id.return_value = None

    dto = BudgetUpdateDTO(amount=1500)

    result = await svc.update_budget(
        budget_id=999,
        user_id=1,
        dto=dto,
    )

    assert result is None


@pytest.mark.asyncio
async def test_update_budget_returns_none_when_user_does_not_own_it(service):
    svc, repo, _ = service
    repo.get_by_id.return_value = make_budget(user_id=2)

    dto = BudgetUpdateDTO(amount=1500)

    result = await svc.update_budget(
        budget_id=1,
        user_id=1,
        dto=dto,
    )

    assert result is None


@pytest.mark.asyncio
async def test_update_budget_raises_when_category_not_found(service):
    svc, repo, category_port = service

    repo.get_by_id.return_value = make_budget()
    category_port.exists.return_value = False

    dto = BudgetUpdateDTO(category_id=999)

    with pytest.raises(CategoryNotFoundForBudget):
        await svc.update_budget(
            budget_id=1,
            user_id=1,
            dto=dto,
        )


@pytest.mark.asyncio
async def test_delete_budget_success(service):
    svc, repo, _ = service

    repo.get_by_id.return_value = make_budget()
    repo.delete.return_value = True

    result = await svc.delete_budget(
        budget_id=1,
        user_id=1,
    )

    assert result is True
    repo.delete.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_delete_budget_returns_false_when_not_found(service):
    svc, repo, _ = service

    repo.get_by_id.return_value = None

    result = await svc.delete_budget(
        budget_id=999,
        user_id=1,
    )

    assert result is False


@pytest.mark.asyncio
async def test_delete_budget_returns_false_when_user_does_not_own_it(service):
    svc, repo, _ = service

    repo.get_by_id.return_value = make_budget(user_id=2)

    result = await svc.delete_budget(
        budget_id=1,
        user_id=1,
    )

    assert result is False