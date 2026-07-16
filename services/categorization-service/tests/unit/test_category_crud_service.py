"""Unit tests for taxonomy CRUD in CategoryService (ADR-003: sole writer).

Covers validation rules, delete guards, and full-state event payloads
using a mocked UnitOfWork — no DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.category_service import CategoryService
from app.application.dto import (
    CreateCategoryDTO,
    CreateSubCategoryDTO,
    UpdateCategoryDTO,
    UpdateSubCategoryDTO,
)
from app.domain.entities import CategorizationRule, Category, Merchant, SubCategory
from app.domain.exceptions import (
    CategoryHasSubcategories,
    CategoryNotFound,
    DuplicateCategoryName,
    DuplicateSubCategoryName,
    InvalidCategoryType,
    SubCategoryInUse,
    SubCategoryNotFound,
)
from app.domain.value_objects import CategoryType, PatternType


def _make_category(**overrides: object) -> Category:
    defaults: dict = {
        "id": 1,
        "name": "Mad & drikke",
        "type": CategoryType.EXPENSE,
        "display_order": 1,
    }
    defaults.update(overrides)
    return Category(**defaults)


def _make_sub(**overrides: object) -> SubCategory:
    defaults: dict = {
        "id": 3,
        "name": "Dagligvarer",
        "category_id": 1,
        "is_default": True,
    }
    defaults.update(overrides)
    return SubCategory(**defaults)


def _build_service() -> tuple[CategoryService, MagicMock]:
    uow = MagicMock()
    uow.categories = AsyncMock()
    uow.subcategories = AsyncMock()
    uow.merchants = AsyncMock()
    uow.rules = AsyncMock()
    uow.outbox = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return CategoryService(uow=uow), uow


class TestCreateCategory:
    @pytest.mark.asyncio()
    async def test_success_emits_full_state_event(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_name.return_value = None
        uow.categories.create.return_value = _make_category()
        dto = CreateCategoryDTO(name="Mad & drikke", type="expense", display_order=1)

        result = await service.create_category(dto)

        uow.categories.create.assert_awaited_once_with(
            "Mad & drikke",
            CategoryType.EXPENSE,
            display_order=1,
        )
        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "category.created"
        assert event.event_version == 2
        assert event.display_order == 1
        assert result.display_order == 1

    @pytest.mark.asyncio()
    async def test_duplicate_name_rejected(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_name.return_value = _make_category()

        with pytest.raises(DuplicateCategoryName):
            await service.create_category(CreateCategoryDTO(name="Mad & drikke", type="expense"))
        uow.commit.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_invalid_type_rejected(self) -> None:
        service, _uow = _build_service()
        with pytest.raises(InvalidCategoryType):
            await service.create_category(CreateCategoryDTO(name="X", type="bogus"))


class TestUpdateCategory:
    @pytest.mark.asyncio()
    async def test_emits_full_state_event(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.categories.find_by_name.return_value = None
        uow.categories.update.return_value = _make_category(name="Mad", display_order=5)

        await service.update_category(1, UpdateCategoryDTO(name="Mad", display_order=5))

        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "category.updated"
        assert event.name == "Mad"
        assert event.display_order == 5

    @pytest.mark.asyncio()
    async def test_rename_to_existing_name_rejected(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.categories.find_by_name.return_value = _make_category(id=2, name="Bolig")

        with pytest.raises(DuplicateCategoryName):
            await service.update_category(1, UpdateCategoryDTO(name="Bolig"))

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = None
        with pytest.raises(CategoryNotFound):
            await service.update_category(99, UpdateCategoryDTO(name="X"))


class TestDeleteCategory:
    @pytest.mark.asyncio()
    async def test_blocked_when_subcategories_exist(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.subcategories.find_by_category_id.return_value = [_make_sub()]

        with pytest.raises(CategoryHasSubcategories):
            await service.delete_category(1)
        uow.categories.delete.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_success_when_empty(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.subcategories.find_by_category_id.return_value = []

        await service.delete_category(1)

        uow.categories.delete.assert_awaited_once_with(1)
        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "category.deleted"
        assert event.display_order == 1


class TestCreateSubcategory:
    @pytest.mark.asyncio()
    async def test_success_marks_non_default_and_emits_event(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.subcategories.find_by_name_and_category.return_value = None
        uow.subcategories.create.return_value = _make_sub(id=50, name="Kaffe", is_default=False)

        result = await service.create_subcategory(1, CreateSubCategoryDTO(name="Kaffe"))

        uow.subcategories.create.assert_awaited_once_with("Kaffe", 1, is_default=False)
        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "subcategory.created"
        assert event.subcategory_id == 50
        assert event.category_id == 1
        assert event.is_default is False
        assert result.name == "Kaffe"

    @pytest.mark.asyncio()
    async def test_parent_must_exist(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = None
        with pytest.raises(CategoryNotFound):
            await service.create_subcategory(99, CreateSubCategoryDTO(name="Kaffe"))

    @pytest.mark.asyncio()
    async def test_duplicate_within_category_rejected(self) -> None:
        service, uow = _build_service()
        uow.categories.find_by_id.return_value = _make_category()
        uow.subcategories.find_by_name_and_category.return_value = _make_sub()

        with pytest.raises(DuplicateSubCategoryName):
            await service.create_subcategory(1, CreateSubCategoryDTO(name="Dagligvarer"))


class TestUpdateSubcategory:
    @pytest.mark.asyncio()
    async def test_rename_success(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub()
        uow.subcategories.find_by_name_and_category.return_value = None
        uow.subcategories.update.return_value = _make_sub(name="Supermarked")

        result = await service.update_subcategory(3, UpdateSubCategoryDTO(name="Supermarked"))

        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "subcategory.updated"
        assert event.name == "Supermarked"
        assert result.name == "Supermarked"

    @pytest.mark.asyncio()
    async def test_reparent_validates_target_category(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub()
        uow.categories.find_by_id.return_value = None

        with pytest.raises(CategoryNotFound):
            await service.update_subcategory(3, UpdateSubCategoryDTO(category_id=99))

    @pytest.mark.asyncio()
    async def test_same_name_in_other_category_is_allowed(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub(category_id=1)
        uow.categories.find_by_id.return_value = _make_category(id=2, name="Bolig")
        uow.subcategories.find_by_name_and_category.return_value = None
        uow.subcategories.update.return_value = _make_sub(category_id=2)

        result = await service.update_subcategory(3, UpdateSubCategoryDTO(category_id=2))
        assert result.category_id == 2

    @pytest.mark.asyncio()
    async def test_duplicate_in_target_category_rejected(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub(id=3, category_id=1)
        uow.categories.find_by_id.return_value = _make_category(id=2)
        uow.subcategories.find_by_name_and_category.return_value = _make_sub(id=8, category_id=2)

        with pytest.raises(DuplicateSubCategoryName):
            await service.update_subcategory(3, UpdateSubCategoryDTO(category_id=2))

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = None
        with pytest.raises(SubCategoryNotFound):
            await service.update_subcategory(99, UpdateSubCategoryDTO(name="X"))


class TestDeleteSubcategory:
    @pytest.mark.asyncio()
    async def test_blocked_by_merchant_reference(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub()
        uow.merchants.find_by_subcategory_id.return_value = [
            Merchant(id=1, normalized_name="netto", display_name="Netto", subcategory_id=3),
        ]

        with pytest.raises(SubCategoryInUse):
            await service.delete_subcategory(3)
        uow.subcategories.delete.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_blocked_by_rule_reference(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub()
        uow.merchants.find_by_subcategory_id.return_value = []
        uow.rules.find_by_subcategory_id.return_value = [
            CategorizationRule(
                id=1,
                user_id=None,
                priority=1,
                pattern_type=PatternType.KEYWORD,
                pattern_value="netto",
                matches_subcategory_id=3,
            ),
        ]

        with pytest.raises(SubCategoryInUse):
            await service.delete_subcategory(3)

    @pytest.mark.asyncio()
    async def test_fallback_anden_cannot_be_deleted(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub(id=32, name="Anden", category_id=8)

        with pytest.raises(SubCategoryInUse):
            await service.delete_subcategory(32)
        uow.merchants.find_by_subcategory_id.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_success_emits_full_final_state(self) -> None:
        service, uow = _build_service()
        uow.subcategories.find_by_id.return_value = _make_sub()
        uow.merchants.find_by_subcategory_id.return_value = []
        uow.rules.find_by_subcategory_id.return_value = []

        await service.delete_subcategory(3)

        uow.subcategories.delete.assert_awaited_once_with(3)
        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "subcategory.deleted"
        assert event.subcategory_id == 3
        assert event.name == "Dagligvarer"
        assert event.category_id == 1
