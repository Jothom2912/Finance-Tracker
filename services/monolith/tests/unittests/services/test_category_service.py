"""Unit tests for the read-only CategoryService.

Category write ownership was extracted to transaction-service in
milestone 2 and confirmed read-only by milestone 4.  Tests for
``create_category``, ``update_category`` and ``delete_category``
have been removed — those live in transaction-service.
"""

from unittest.mock import Mock

import pytest
from backend.category.application.ports.outbound import ICategoryRepository
from backend.category.application.service import CategoryService
from backend.category.domain.entities import Category as CategoryEntity
from backend.category.domain.value_objects import CategoryType

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
        mock_category_repo.get_all.return_value = [_category_entity(i, f"Cat {i}") for i in range(10)]

        result = service.list_categories(skip=2, limit=3)

        assert len(result) == 3
        assert result[0].idCategory == 2

    def test_returns_empty_list_when_no_categories(self, service, mock_category_repo):
        mock_category_repo.get_all.return_value = []

        result = service.list_categories()

        assert result == []


# Write-path tests removed in M4: CategoryService no longer exposes
# create_category / update_category / delete_category.  See
# services/transaction-service/tests/unit/test_category_service.py
# for the owning-service equivalents.
