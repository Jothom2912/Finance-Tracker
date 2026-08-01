"""TAX-01 baseline guard for the current default taxonomy.

The redesign starts from pinned database identifiers.  These tests make drift between the
runtime seed, the additive seed migrations and rule targets visible before a mapping is
approved; they deliberately do not define the future taxonomy.
"""

from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path
from types import ModuleType

from app.domain.taxonomy import DEFAULT_TAXONOMY, SEED_MERCHANT_MAPPINGS

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _load_migration(filename: str) -> ModuleType:
    path = SERVICE_ROOT / "migrations" / "versions" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime_subcategories() -> list[tuple[str, str]]:
    return [
        (category_name, subcategory_name)
        for category_name, definition in DEFAULT_TAXONOMY.items()
        for subcategory_name in definition["subcategories"]
    ]


def test_runtime_seed_matches_pinned_category_and_subcategory_migrations() -> None:
    category_migration = _load_migration("002_seed_categories.py")
    subcategory_migration = _load_migration("003_seed_subcategories.py")

    pinned_categories = category_migration._DEFAULT_CATEGORIES
    pinned_subcategories = subcategory_migration._SUBCATEGORIES

    assert len(pinned_categories) == 10
    assert [row[0] for row in pinned_categories] == list(range(1, 11))
    assert [(name, definition["type"].value, definition["order"]) for name, definition in DEFAULT_TAXONOMY.items()] == [
        (name, category_type, display_order) for _, name, category_type, display_order in pinned_categories
    ]

    category_names_by_id = {category_id: name for category_id, name, _, _ in pinned_categories}
    assert len(pinned_subcategories) == 41
    assert [row[0] for row in pinned_subcategories] == list(range(1, 42))
    assert _runtime_subcategories() == [
        (category_names_by_id[category_id], name) for _, name, category_id in pinned_subcategories
    ]


def test_names_are_unambiguous_and_every_rule_target_exists() -> None:
    category_names = list(DEFAULT_TAXONOMY)
    subcategory_names = [subcategory for _, subcategory in _runtime_subcategories()]

    duplicate_categories = [
        name for name, count in Counter(name.casefold() for name in category_names).items() if count > 1
    ]
    duplicate_subcategories = [
        name for name, count in Counter(name.casefold() for name in subcategory_names).items() if count > 1
    ]
    rule_targets = {mapping["subcategory"] for mapping in SEED_MERCHANT_MAPPINGS.values()}

    assert duplicate_categories == []
    assert duplicate_subcategories == []
    assert rule_targets - set(subcategory_names) == set()
    assert len(SEED_MERCHANT_MAPPINGS) == 130


def test_current_fallback_and_type_baseline_is_explicit() -> None:
    categories_by_type = Counter(definition["type"].value for definition in DEFAULT_TAXONOMY.values())
    fallback_candidates = {
        (category, subcategory)
        for category, subcategory in _runtime_subcategories()
        if "anden" in subcategory.casefold() or "ukendt" in subcategory.casefold()
    }

    assert categories_by_type == {"expense": 8, "income": 1, "transfer": 1}
    assert fallback_candidates == {("Diverse", "Anden")}
