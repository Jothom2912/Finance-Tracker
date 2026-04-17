"""
Unit tests for Category bounded context domain model.

Tests the three-level hierarchy (Category -> SubCategory -> Merchant),
value objects (CategorizationResult, MerchantMapping), and taxonomy data.
"""

import pytest
from backend.category.domain.entities import Category, Merchant, SubCategory
from backend.category.domain.exceptions import (
    CategoryNotFound,
    MerchantNotFound,
    SubCategoryNotFound,
)
from backend.category.domain.taxonomy import DEFAULT_TAXONOMY, SEED_MERCHANT_MAPPINGS
from backend.category.domain.value_objects import (
    CategorizationResult,
    CategorizationTier,
    CategoryLevel,
    CategoryType,
    Confidence,
    MappingSource,
    MerchantMapping,
)

# ──────────────────────────────────────────────
# CategoryType enum
# ──────────────────────────────────────────────


class TestCategoryType:
    def test_expense_value(self) -> None:
        assert CategoryType.EXPENSE.value == "expense"

    def test_income_value(self) -> None:
        assert CategoryType.INCOME.value == "income"

    def test_transfer_value(self) -> None:
        assert CategoryType.TRANSFER.value == "transfer"

    def test_all_types_present(self) -> None:
        assert len(CategoryType) == 3


# ──────────────────────────────────────────────
# CategoryLevel enum
# ──────────────────────────────────────────────


class TestCategoryLevel:
    def test_hierarchy_ordering(self) -> None:
        assert CategoryLevel.CATEGORY.value < CategoryLevel.SUBCATEGORY.value
        assert CategoryLevel.SUBCATEGORY.value < CategoryLevel.MERCHANT.value

    def test_all_levels_present(self) -> None:
        assert len(CategoryLevel) == 3


# ──────────────────────────────────────────────
# CategorizationTier enum
# ──────────────────────────────────────────────


class TestCategorizationTier:
    def test_pipeline_tiers(self) -> None:
        assert CategorizationTier.RULE.value == "rule"
        assert CategorizationTier.ML.value == "ml"
        assert CategorizationTier.LLM.value == "llm"
        assert CategorizationTier.MANUAL.value == "manual"
        assert CategorizationTier.FALLBACK.value == "fallback"


# ──────────────────────────────────────────────
# Confidence enum
# ──────────────────────────────────────────────


class TestConfidence:
    def test_confidence_levels(self) -> None:
        assert Confidence.HIGH.value == "high"
        assert Confidence.MEDIUM.value == "medium"
        assert Confidence.LOW.value == "low"


# ──────────────────────────────────────────────
# Category entity
# ──────────────────────────────────────────────


class TestCategory:
    def test_create_expense_category(self) -> None:
        category = Category(id=1, name="Mad & drikke", type=CategoryType.EXPENSE)
        assert category.is_expense()
        assert not category.is_income()
        assert not category.is_transfer()

    def test_create_income_category(self) -> None:
        category = Category(id=2, name="Indkomst", type=CategoryType.INCOME)
        assert category.is_income()
        assert not category.is_expense()

    def test_create_transfer_category(self) -> None:
        category = Category(id=3, name="Overfoersler", type=CategoryType.TRANSFER)
        assert category.is_transfer()
        assert not category.is_expense()

    def test_display_order_default(self) -> None:
        category = Category(id=1, name="Test", type=CategoryType.EXPENSE)
        assert category.display_order == 0

    def test_display_order_custom(self) -> None:
        category = Category(id=1, name="Test", type=CategoryType.EXPENSE, display_order=5)
        assert category.display_order == 5

    def test_id_optional_for_new_entity(self) -> None:
        category = Category(id=None, name="New", type=CategoryType.EXPENSE)
        assert category.id is None


# ──────────────────────────────────────────────
# SubCategory entity
# ──────────────────────────────────────────────


class TestSubCategory:
    def test_create_factory(self) -> None:
        sub = SubCategory.create(name="Dagligvarer", category_id=1)
        assert sub.id is None
        assert sub.name == "Dagligvarer"
        assert sub.category_id == 1
        assert sub.is_default is True

    def test_create_user_defined(self) -> None:
        sub = SubCategory.create(name="Custom", category_id=1, is_default=False)
        assert sub.is_default is False

    def test_direct_construction(self) -> None:
        sub = SubCategory(id=10, name="Restaurant", category_id=1, is_default=True)
        assert sub.id == 10
        assert sub.name == "Restaurant"


# ──────────────────────────────────────────────
# Merchant entity
# ──────────────────────────────────────────────


class TestMerchant:
    def test_create_factory(self) -> None:
        merchant = Merchant.create(
            normalized_name="netto",
            display_name="Netto",
            subcategory_id=1,
        )
        assert merchant.id is None
        assert merchant.normalized_name == "netto"
        assert merchant.display_name == "Netto"
        assert merchant.subcategory_id == 1
        assert merchant.transaction_count == 0
        assert merchant.is_user_confirmed is False

    def test_confirm(self) -> None:
        merchant = Merchant.create("netto", "Netto", subcategory_id=1)
        merchant.confirm()
        assert merchant.is_user_confirmed is True

    def test_increment_count(self) -> None:
        merchant = Merchant.create("netto", "Netto", subcategory_id=1)
        merchant.increment_count()
        merchant.increment_count()
        assert merchant.transaction_count == 2

    def test_confirm_is_idempotent(self) -> None:
        merchant = Merchant.create("netto", "Netto", subcategory_id=1)
        merchant.confirm()
        merchant.confirm()
        assert merchant.is_user_confirmed is True


# ──────────────────────────────────────────────
# CategorizationResult value object
# ──────────────────────────────────────────────


class TestCategorizationResult:
    def test_is_frozen(self) -> None:
        result = CategorizationResult(category_id=1, subcategory_id=2)
        with pytest.raises(AttributeError):
            result.category_id = 99  # type: ignore[misc]

    def test_defaults(self) -> None:
        result = CategorizationResult(category_id=1, subcategory_id=2)
        assert result.merchant_id is None
        assert result.tier == CategorizationTier.RULE
        assert result.confidence == Confidence.HIGH

    def test_was_auto_categorized_for_rule(self) -> None:
        result = CategorizationResult(category_id=1, subcategory_id=2, tier=CategorizationTier.RULE)
        assert result.was_auto_categorized is True

    def test_was_auto_categorized_for_manual(self) -> None:
        result = CategorizationResult(category_id=1, subcategory_id=2, tier=CategorizationTier.MANUAL)
        assert result.was_auto_categorized is False

    def test_needs_review_when_low_confidence(self) -> None:
        result = CategorizationResult(category_id=1, subcategory_id=2, confidence=Confidence.LOW)
        assert result.needs_review is True

    def test_no_review_needed_when_high_confidence(self) -> None:
        result = CategorizationResult(category_id=1, subcategory_id=2, confidence=Confidence.HIGH)
        assert result.needs_review is False

    def test_equality_by_value(self) -> None:
        r1 = CategorizationResult(category_id=1, subcategory_id=2, merchant_id=3)
        r2 = CategorizationResult(category_id=1, subcategory_id=2, merchant_id=3)
        assert r1 == r2

    def test_inequality_different_values(self) -> None:
        r1 = CategorizationResult(category_id=1, subcategory_id=2)
        r2 = CategorizationResult(category_id=1, subcategory_id=3)
        assert r1 != r2


# ──────────────────────────────────────────────
# MerchantMapping value object
# ──────────────────────────────────────────────


class TestMerchantMapping:
    def test_is_frozen(self) -> None:
        mapping = MerchantMapping(keyword="netto", merchant_id=1, subcategory_id=2)
        with pytest.raises(AttributeError):
            mapping.keyword = "lidl"  # type: ignore[misc]

    def test_default_source_is_seed(self) -> None:
        mapping = MerchantMapping(keyword="netto", merchant_id=1, subcategory_id=2)
        assert mapping.source == MappingSource.SEED

    def test_manual_source(self) -> None:
        mapping = MerchantMapping(keyword="custom", merchant_id=1, subcategory_id=2, source=MappingSource.MANUAL)
        assert mapping.source == MappingSource.MANUAL


# ──────────────────────────────────────────────
# Domain exceptions
# ──────────────────────────────────────────────


class TestExceptions:
    def test_category_not_found(self) -> None:
        exc = CategoryNotFound(category_id=42)
        assert exc.category_id == 42
        assert "42" in str(exc)

    def test_subcategory_not_found(self) -> None:
        exc = SubCategoryNotFound(subcategory_id=7)
        assert exc.subcategory_id == 7
        assert "7" in str(exc)

    def test_merchant_not_found(self) -> None:
        exc = MerchantNotFound(merchant_id=99)
        assert exc.merchant_id == 99
        assert "99" in str(exc)


# ──────────────────────────────────────────────
# Taxonomy data integrity
# ──────────────────────────────────────────────


class TestDefaultTaxonomy:
    def test_all_categories_have_required_keys(self) -> None:
        for name, data in DEFAULT_TAXONOMY.items():
            assert "type" in data, f"Category '{name}' missing 'type'"
            assert "order" in data, f"Category '{name}' missing 'order'"
            assert "subcategories" in data, f"Category '{name}' missing 'subcategories'"

    def test_all_category_types_are_valid(self) -> None:
        for name, data in DEFAULT_TAXONOMY.items():
            assert isinstance(data["type"], CategoryType), f"Category '{name}' has invalid type: {data['type']}"

    def test_has_expense_categories(self) -> None:
        expense_cats = [name for name, data in DEFAULT_TAXONOMY.items() if data["type"] == CategoryType.EXPENSE]
        assert len(expense_cats) >= 5

    def test_has_income_category(self) -> None:
        income_cats = [name for name, data in DEFAULT_TAXONOMY.items() if data["type"] == CategoryType.INCOME]
        assert len(income_cats) >= 1

    def test_has_transfer_category(self) -> None:
        transfer_cats = [name for name, data in DEFAULT_TAXONOMY.items() if data["type"] == CategoryType.TRANSFER]
        assert len(transfer_cats) >= 1

    def test_subcategory_names_are_globally_unique(self) -> None:
        all_subcats: list[str] = []
        for name, data in DEFAULT_TAXONOMY.items():
            for sub in data["subcategories"]:
                assert sub not in all_subcats, f"Duplicate subcategory '{sub}' found in '{name}'"
                all_subcats.append(sub)

    def test_display_orders_are_unique(self) -> None:
        orders = [data["order"] for data in DEFAULT_TAXONOMY.values()]
        assert len(orders) == len(set(orders)), "Duplicate display orders found"

    def test_all_subcategories_are_non_empty(self) -> None:
        for name, data in DEFAULT_TAXONOMY.items():
            assert len(data["subcategories"]) > 0, f"Category '{name}' has no subcategories"

    def test_anden_fallback_exists(self) -> None:
        all_subcats = []
        for data in DEFAULT_TAXONOMY.values():
            all_subcats.extend(data["subcategories"])
        assert "Anden" in all_subcats


class TestSeedMerchantMappings:
    def test_all_mappings_have_required_keys(self) -> None:
        for keyword, data in SEED_MERCHANT_MAPPINGS.items():
            assert "subcategory" in data, f"Mapping '{keyword}' missing 'subcategory'"
            assert "display" in data, f"Mapping '{keyword}' missing 'display'"

    def test_all_keywords_are_lowercase(self) -> None:
        for keyword in SEED_MERCHANT_MAPPINGS:
            assert keyword == keyword.lower(), f"Keyword '{keyword}' is not lowercase"

    def test_all_subcategories_exist_in_taxonomy(self) -> None:
        all_subcats: set[str] = set()
        for data in DEFAULT_TAXONOMY.values():
            all_subcats.update(data["subcategories"])

        for keyword, mapping in SEED_MERCHANT_MAPPINGS.items():
            assert mapping["subcategory"] in all_subcats, (
                f"Mapping '{keyword}' references non-existent subcategory '{mapping['subcategory']}'"
            )

    def test_has_mappings_for_core_merchants(self) -> None:
        core_keywords = ["netto", "lidl", "wolt", "dsb", "spotify", "ikea"]
        for kw in core_keywords:
            assert kw in SEED_MERCHANT_MAPPINGS, f"Core keyword '{kw}' missing"

    def test_minimum_mapping_count(self) -> None:
        assert len(SEED_MERCHANT_MAPPINGS) >= 80
