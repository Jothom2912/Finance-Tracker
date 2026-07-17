"""Unit tests for RuleService (F1-02): user-scoped CRUD, ownership
guards, duplicate mapping, cache-invalidation callback. Mocked UoW."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.dto import CreateRuleDTO, UpdateRuleDTO
from app.application.rule_service import RuleService
from app.domain.entities import CategorizationRule, Category, SubCategory
from app.domain.exceptions import DuplicateRule, RuleNotFound, SubCategoryNotFound
from app.domain.value_objects import CategoryType, PatternType
from sqlalchemy.exc import IntegrityError


def _make_rule(**overrides: object) -> CategorizationRule:
    defaults: dict = {
        "id": 1,
        "user_id": 7,
        "priority": 50,
        "pattern_type": PatternType.KEYWORD,
        "pattern_value": "netto",
        "matches_subcategory_id": 3,
        "active": True,
    }
    defaults.update(overrides)
    return CategorizationRule(**defaults)


def _build_service() -> tuple[RuleService, MagicMock, MagicMock]:
    uow = MagicMock()
    uow.categories = AsyncMock()
    uow.subcategories = AsyncMock()
    uow.rules = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    uow.categories.find_all.return_value = [Category(id=1, name="Mad & drikke", type=CategoryType.EXPENSE)]
    uow.subcategories.find_all.return_value = [SubCategory(id=3, name="Dagligvarer", category_id=1)]
    uow.subcategories.find_by_id.return_value = SubCategory(id=3, name="Dagligvarer", category_id=1)

    on_changed = MagicMock()
    return RuleService(uow=uow, on_rules_changed=on_changed), uow, on_changed


class TestListRules:
    @pytest.mark.asyncio()
    async def test_lists_only_own_rules_with_resolved_names(self) -> None:
        service, uow, _ = _build_service()
        uow.rules.find_by_user.return_value = [
            _make_rule(),
            _make_rule(id=2, pattern_type=PatternType.MERCHANT, pattern_value="netto vesterbro", priority=10),
        ]

        result = await service.list_rules(user_id=7)

        uow.rules.find_by_user.assert_awaited_once_with(7)
        assert len(result) == 2
        assert result[0].subcategory_name == "Dagligvarer"
        assert result[0].category_name == "Mad & drikke"
        assert result[0].is_learned is False
        assert result[1].is_learned is True


class TestCreateRule:
    @pytest.mark.asyncio()
    async def test_creates_keyword_rule_scoped_to_user(self) -> None:
        service, uow, on_changed = _build_service()
        uow.rules.create.return_value = _make_rule()

        result = await service.create_rule(user_id=7, dto=CreateRuleDTO(pattern_value="  netto ", subcategory_id=3))

        created: CategorizationRule = uow.rules.create.await_args.args[0]
        assert created.user_id == 7
        assert created.pattern_type == PatternType.KEYWORD
        assert created.pattern_value == "netto"  # trimmed
        assert created.priority == 50
        uow.commit.assert_awaited_once()
        on_changed.assert_called_once_with(7)
        assert result.pattern_value == "netto"

    @pytest.mark.asyncio()
    async def test_unknown_subcategory_raises(self) -> None:
        service, uow, on_changed = _build_service()
        uow.subcategories.find_by_id.return_value = None

        with pytest.raises(SubCategoryNotFound):
            await service.create_rule(user_id=7, dto=CreateRuleDTO(pattern_value="netto", subcategory_id=999))
        uow.rules.create.assert_not_awaited()
        on_changed.assert_not_called()

    @pytest.mark.asyncio()
    async def test_duplicate_pattern_maps_integrity_error_to_409_exception(self) -> None:
        service, uow, on_changed = _build_service()
        uow.rules.create.side_effect = IntegrityError("uq_rules_user_pattern", None, Exception())

        with pytest.raises(DuplicateRule):
            await service.create_rule(user_id=7, dto=CreateRuleDTO(pattern_value="netto", subcategory_id=3))
        on_changed.assert_not_called()


class TestUpdateRule:
    @pytest.mark.asyncio()
    async def test_updates_own_rule_and_remaps_subcategory_field(self) -> None:
        service, uow, on_changed = _build_service()
        uow.rules.find_by_id.return_value = _make_rule()
        uow.rules.update.return_value = _make_rule(pattern_value="rema", active=False)

        await service.update_rule(
            user_id=7,
            rule_id=1,
            dto=UpdateRuleDTO(pattern_value="rema", subcategory_id=3, active=False),
        )

        fields = uow.rules.update.await_args.kwargs
        assert fields["pattern_value"] == "rema"
        assert fields["matches_subcategory_id"] == 3
        assert "subcategory_id" not in fields
        assert fields["active"] is False
        on_changed.assert_called_once_with(7)

    @pytest.mark.asyncio()
    async def test_foreign_rule_is_indistinguishable_from_missing(self) -> None:
        """Ownership must not be probeable: another user's rule → 404,
        exactly like a nonexistent id."""
        service, uow, on_changed = _build_service()
        uow.rules.find_by_id.return_value = _make_rule(user_id=999)

        with pytest.raises(RuleNotFound):
            await service.update_rule(user_id=7, rule_id=1, dto=UpdateRuleDTO(active=False))
        uow.rules.update.assert_not_awaited()
        on_changed.assert_not_called()

    @pytest.mark.asyncio()
    async def test_seed_rule_is_untouchable(self) -> None:
        service, uow, _ = _build_service()
        uow.rules.find_by_id.return_value = _make_rule(user_id=None)

        with pytest.raises(RuleNotFound):
            await service.update_rule(user_id=7, rule_id=1, dto=UpdateRuleDTO(active=False))


class TestDeleteRule:
    @pytest.mark.asyncio()
    async def test_deletes_own_rule_and_invalidates_cache(self) -> None:
        service, uow, on_changed = _build_service()
        uow.rules.find_by_id.return_value = _make_rule()

        await service.delete_rule(user_id=7, rule_id=1)

        uow.rules.delete.assert_awaited_once_with(1)
        uow.commit.assert_awaited_once()
        on_changed.assert_called_once_with(7)

    @pytest.mark.asyncio()
    async def test_missing_rule_raises_not_found(self) -> None:
        service, uow, _ = _build_service()
        uow.rules.find_by_id.return_value = None

        with pytest.raises(RuleNotFound):
            await service.delete_rule(user_id=7, rule_id=404)
        uow.rules.delete.assert_not_awaited()
