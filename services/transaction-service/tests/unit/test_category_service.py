from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.category_service import CategoryService
from app.application.dto import CreateCategoryDTO, UpdateCategoryDTO
from app.domain.entities import Category, CategoryType
from app.domain.exceptions import (
    CategoryInUseException,
    CategoryNotFoundException,
    DuplicateCategoryNameException,
)


def _make_category(**overrides) -> Category:  # type: ignore[no-untyped-def]
    defaults = {
        "id": 1,
        "name": "Food",
        "type": CategoryType.EXPENSE,
    }
    defaults.update(overrides)
    return Category(**defaults)


def _build_service():  # type: ignore[no-untyped-def]
    uow = MagicMock()
    uow.categories = AsyncMock()
    uow.outbox = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    service = CategoryService(uow=uow)
    return service, uow


class TestCreateCategory:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_name.return_value = None
        uow.categories.create.return_value = _make_category()
        dto = CreateCategoryDTO(name="Food", type=CategoryType.EXPENSE)

        result = await service.create_category(dto)

        uow.categories.create.assert_awaited_once_with("Food", CategoryType.EXPENSE)
        uow.commit.assert_awaited_once()
        assert result.id == 1
        assert result.name == "Food"
        assert result.type == CategoryType.EXPENSE

    @pytest.mark.asyncio()
    async def test_writes_outbox_event(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_name.return_value = None
        uow.categories.create.return_value = _make_category()
        dto = CreateCategoryDTO(name="Food", type=CategoryType.EXPENSE)

        await service.create_category(dto)

        uow.outbox.add.assert_awaited_once()
        call_kwargs = uow.outbox.add.call_args[1]
        event = call_kwargs["event"]
        assert event.event_type == "category.created"
        assert event.category_id == 1
        assert event.name == "Food"
        assert event.category_type == "expense"
        assert call_kwargs["aggregate_type"] == "category"

    @pytest.mark.asyncio()
    async def test_duplicate_name_raises(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_name.return_value = _make_category()
        dto = CreateCategoryDTO(name="Food", type=CategoryType.EXPENSE)

        with pytest.raises(DuplicateCategoryNameException):
            await service.create_category(dto)

        uow.categories.create.assert_not_awaited()
        uow.commit.assert_not_awaited()


class TestGetCategories:
    @pytest.mark.asyncio()
    async def test_returns_all(self) -> None:
        service, uow = _build_service()
        uow.categories.find_all.return_value = [
            _make_category(id=1, name="Food"),
            _make_category(id=2, name="Transport"),
        ]

        result = await service.get_categories()

        assert len(result) == 2
        assert result[0].name == "Food"
        assert result[1].name == "Transport"


class TestGetCategory:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()

        result = await service.get_category(1)

        assert result.id == 1
        uow.categories.find_by_id.assert_awaited_once_with(1)

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = None

        with pytest.raises(CategoryNotFoundException):
            await service.get_category(99)


class TestUpdateCategory:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        existing = _make_category()
        updated = _make_category(name="Groceries")
        uow.categories.find_by_id.return_value = existing
        uow.categories.find_by_name.return_value = None
        uow.categories.update.return_value = updated
        dto = UpdateCategoryDTO(name="Groceries")

        result = await service.update_category(1, dto)

        uow.categories.update.assert_awaited_once()
        uow.commit.assert_awaited_once()
        assert result.name == "Groceries"

    @pytest.mark.asyncio()
    async def test_writes_outbox_event_with_previous(self) -> None:
        service, uow = _build_service()
        existing = _make_category(name="Food", type=CategoryType.EXPENSE)
        updated = _make_category(name="Groceries", type=CategoryType.EXPENSE)
        uow.categories.find_by_id.return_value = existing
        uow.categories.find_by_name.return_value = None
        uow.categories.update.return_value = updated
        dto = UpdateCategoryDTO(name="Groceries")

        await service.update_category(1, dto)

        uow.outbox.add.assert_awaited_once()
        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "category.updated"
        assert event.name == "Groceries"
        assert event.previous_name == "Food"
        assert event.previous_type == "expense"

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = None
        dto = UpdateCategoryDTO(name="Groceries")

        with pytest.raises(CategoryNotFoundException):
            await service.update_category(99, dto)

    @pytest.mark.asyncio()
    async def test_no_op_when_empty_body(self) -> None:
        service, uow = _build_service()
        existing = _make_category()
        uow.categories.find_by_id.return_value = existing
        dto = UpdateCategoryDTO()

        result = await service.update_category(1, dto)

        uow.categories.update.assert_not_awaited()
        uow.commit.assert_not_awaited()
        assert result.id == existing.id
        assert result.name == existing.name

    @pytest.mark.asyncio()
    async def test_duplicate_name_on_rename(self) -> None:
        service, uow = _build_service()
        existing = _make_category(id=1, name="Food")
        uow.categories.find_by_id.return_value = existing
        uow.categories.find_by_name.return_value = _make_category(id=2, name="Transport")
        dto = UpdateCategoryDTO(name="Transport")

        with pytest.raises(DuplicateCategoryNameException):
            await service.update_category(1, dto)

    @pytest.mark.asyncio()
    async def test_same_name_no_duplicate_check(self) -> None:
        service, uow = _build_service()
        existing = _make_category(id=1, name="Food")
        updated = _make_category(id=1, name="Food", type=CategoryType.INCOME)
        uow.categories.find_by_id.return_value = existing
        uow.categories.update.return_value = updated
        dto = UpdateCategoryDTO(type=CategoryType.INCOME)

        result = await service.update_category(1, dto)

        uow.categories.find_by_name.assert_not_awaited()
        assert result.type == CategoryType.INCOME


class TestDeleteCategory:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.categories.count_transactions.return_value = 0
        uow.categories.delete.return_value = True

        await service.delete_category(1)

        uow.categories.delete.assert_awaited_once_with(1)
        uow.commit.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = None

        with pytest.raises(CategoryNotFoundException):
            await service.delete_category(99)

    @pytest.mark.asyncio()
    async def test_writes_outbox_event(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.categories.count_transactions.return_value = 0
        uow.categories.delete.return_value = True

        await service.delete_category(1)

        uow.outbox.add.assert_awaited_once()
        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "category.deleted"
        assert event.category_id == 1
        assert event.name == "Food"

    @pytest.mark.asyncio()
    async def test_in_use_returns_409(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.categories.count_transactions.return_value = 3

        with pytest.raises(CategoryInUseException):
            await service.delete_category(1)

        uow.categories.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()
