"""
Unit tests for CategoryService business logic.

Updated for hexagonal architecture (backend.category.*).
"""

import pytest
from unittest.mock import Mock

from backend.category.application.service import CategoryService
from backend.category.application.ports.outbound import ICategoryRepository
from backend.category.domain.entities import Category as CategoryEntity
from backend.category.domain.value_objects import CategoryType
from backend.category.domain.exceptions import (
    DuplicateCategoryName,
    DuplicateCategoryNameOnUpdate,
)
from backend.shared.schemas.category import CategoryCreate


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_category_repo():
    return Mock(spec=ICategoryRepository)


@pytest.fixture
def service(mock_category_repo):
    return CategoryService(category_repo=mock_category_repo)


def _category_entity(
    category_id: int,
    name: str,
    category_type: CategoryType = CategoryType.EXPENSE,
) -> CategoryEntity:
    return CategoryEntity(id=category_id, name=name, type=category_type)


# ============================================================================
# get_category
# ============================================================================


class TestGetCategory:
    def test_returns_category_when_found(self, service, mock_category_repo):
        mock_category_repo.get_by_id.return_value = _category_entity(1, "Mad")

        result = service.get_category(category_id=1)

        assert result.idCategory == 1
        assert result.name == "Mad"
        assert result.type == "expense"
        mock_category_repo.get_by_id.assert_called_once_with(1)

    def test_returns_none_when_not_found(self, service, mock_category_repo):
        mock_category_repo.get_by_id.return_value = None

        result = service.get_category(category_id=999)

        assert result is None


# ============================================================================
# get_by_name
# ============================================================================


class TestGetByName:
    def test_returns_category_when_name_matches(self, service, mock_category_repo):
        mock_category_repo.get_by_name.return_value = _category_entity(2, "Transport")

        result = service.get_by_name("Transport")

        assert result.idCategory == 2

    def test_returns_none_when_name_not_found(self, service, mock_category_repo):
        mock_category_repo.get_by_name.return_value = None

        result = service.get_by_name("Ukendt")

        assert result is None

    def test_returns_none_when_no_categories(self, service, mock_category_repo):
        mock_category_repo.get_by_name.return_value = None

        result = service.get_by_name("Anything")

        assert result is None


# ============================================================================
# list_categories
# ============================================================================


class TestListCategories:
    def test_returns_all_categories(self, service, mock_category_repo):
        mock_category_repo.get_all.return_value = [
            _category_entity(1, "Mad"),
            _category_entity(2, "Transport"),
        ]

        result = service.list_categories()

        assert len(result) == 2

    def test_applies_pagination(self, service, mock_category_repo):
        mock_category_repo.get_all.return_value = [
            _category_entity(i, f"Cat {i}") for i in range(10)
        ]

        result = service.list_categories(skip=2, limit=3)

        assert len(result) == 3
        assert result[0].idCategory == 2

    def test_returns_empty_list_when_no_categories(self, service, mock_category_repo):
        mock_category_repo.get_all.return_value = []

        result = service.list_categories()

        assert result == []


# ============================================================================
# create_category
# ============================================================================


class TestCreateCategory:
    def test_creates_category_successfully(self, service, mock_category_repo):
        mock_category_repo.get_by_name.return_value = None
        mock_category_repo.create.return_value = _category_entity(1, "Mad")
        category = CategoryCreate(name="Mad", type="expense")

        result = service.create_category(category)

        assert result.name == "Mad"
        mock_category_repo.create.assert_called_once()

    def test_raises_when_duplicate_name(self, service, mock_category_repo):
        mock_category_repo.get_by_name.return_value = _category_entity(1, "Mad")
        category = CategoryCreate(name="Mad", type="expense")

        with pytest.raises(DuplicateCategoryName):
            service.create_category(category)

    def test_does_not_call_create_on_duplicate(self, service, mock_category_repo):
        mock_category_repo.get_by_name.return_value = _category_entity(1, "Mad")
        category = CategoryCreate(name="Mad", type="expense")

        with pytest.raises(DuplicateCategoryName):
            service.create_category(category)

        mock_category_repo.create.assert_not_called()

    def test_converts_type_enum_to_string(self, service, mock_category_repo):
        mock_category_repo.get_by_name.return_value = None
        mock_category_repo.create.return_value = _category_entity(
            1, "Løn", CategoryType.INCOME
        )
        category = CategoryCreate(name="Løn", type="income")

        service.create_category(category)

        call_data = mock_category_repo.create.call_args[0][0]
        assert call_data.type == "income"


# ============================================================================
# update_category
# ============================================================================


class TestUpdateCategory:
    def test_returns_none_when_not_found(self, service, mock_category_repo):
        mock_category_repo.get_by_id.return_value = None
        data = CategoryCreate(name="Updated", type="expense")

        result = service.update_category(category_id=999, dto=data)

        assert result is None

    def test_updates_successfully(self, service, mock_category_repo):
        mock_category_repo.get_by_id.return_value = _category_entity(1, "Mad")
        mock_category_repo.get_by_name.return_value = None
        mock_category_repo.update.return_value = _category_entity(1, "Dagligvarer")
        data = CategoryCreate(name="Dagligvarer", type="expense")

        result = service.update_category(category_id=1, dto=data)

        assert result.name == "Dagligvarer"

    def test_raises_when_name_conflicts_with_other(self, service, mock_category_repo):
        mock_category_repo.get_by_id.return_value = _category_entity(1, "Mad")
        mock_category_repo.get_by_name.return_value = _category_entity(
            2, "Transport"
        )
        data = CategoryCreate(name="Transport", type="expense")

        with pytest.raises(DuplicateCategoryNameOnUpdate):
            service.update_category(category_id=1, dto=data)

    def test_allows_keeping_same_name(self, service, mock_category_repo):
        mock_category_repo.get_by_id.return_value = _category_entity(1, "Mad")
        mock_category_repo.update.return_value = _category_entity(
            1, "Mad", CategoryType.INCOME
        )
        data = CategoryCreate(name="Mad", type="income")  # Same name, different type

        result = service.update_category(category_id=1, dto=data)

        assert result is not None


# ============================================================================
# delete_category
# ============================================================================


class TestDeleteCategory:
    def test_delegates_to_repository(self, service, mock_category_repo):
        mock_category_repo.delete.return_value = True

        service.delete_category(category_id=1)

        mock_category_repo.delete.assert_called_once_with(1)

    def test_returns_true_on_success(self, service, mock_category_repo):
        mock_category_repo.delete.return_value = True

        assert service.delete_category(category_id=1) is True

    def test_returns_false_when_not_found(self, service, mock_category_repo):
        mock_category_repo.delete.return_value = False

        assert service.delete_category(category_id=999) is False
