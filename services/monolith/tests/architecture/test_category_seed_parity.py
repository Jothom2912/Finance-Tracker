"""Architecture fitness test — category seed parity across services.

The default category taxonomy is defined in two places by design:

* Monolith ``backend/category/domain/taxonomy.py`` holds ``DEFAULT_TAXONOMY``,
  which drives subcategory seeding (monolith-owned).
* Transaction-service ``migrations/versions/005_seed_default_categories.py``
  holds ``_DEFAULT_CATEGORIES``, which is the single source of truth for
  the cross-service category entities (transaction-service-owned).

The two lists must agree on name, type, and ordering — because the IDs
in migration 005 are pinned by position, and the rule engine (reading
from MySQL, where categories arrive via the event stream) depends on
those IDs matching what transaction-service has stored.  A drift
between the two would reproduce exactly the bug this test suite was
written to prevent: a silent inconsistency that only surfaces as
"Ukendt" in the UI for every bank-synced transaction.

This is a static test: it parses both data structures without any
database or network I/O, and fails in milliseconds if someone adds,
removes, renames, or reorders a category in one place without
touching the other.  It complements — doesn't replace — the
live-parity integration test that verifies runtime state.

If this test fails: the two seed sources diverged.  Either:

* Add/update the missing entry on the other side (most common fix).
* If the change is intentional and requires a new migration, create
  migration 007 (and subsequent) to carry the new row + emit the
  corresponding event, and update ``DEFAULT_TAXONOMY`` in lockstep.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backend.category.domain.taxonomy import DEFAULT_TAXONOMY

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MIGRATION_005 = (
    _REPO_ROOT
    / "services"
    / "transaction-service"
    / "migrations"
    / "versions"
    / "005_seed_default_categories.py"
)


def _extract_default_categories() -> list[tuple[int, str, str]]:
    """Parse migration 005 with AST and return ``_DEFAULT_CATEGORIES``.

    We deliberately don't ``import`` the migration module: it depends
    on ``alembic`` and ``sqlalchemy`` which the monolith's venv
    doesn't need to carry just to run a fast architecture test.
    ``ast`` parses the file lexically, so the test has zero runtime
    coupling to transaction-service's dependency tree.
    """
    source = _MIGRATION_005.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_MIGRATION_005))

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
        else:
            continue

        if target_name != "_DEFAULT_CATEGORIES":
            continue

        value = node.value
        assert value is not None, "_DEFAULT_CATEGORIES has no right-hand side"
        return [
            (int(elt.elts[0].value), str(elt.elts[1].value), str(elt.elts[2].value))
            for elt in value.elts  # type: ignore[attr-defined]
            if isinstance(elt, ast.Tuple)
        ]

    raise AssertionError(
        f"_DEFAULT_CATEGORIES not found in {_MIGRATION_005}. "
        "The seed list was renamed or removed — update this test to match."
    )


def test_migration_005_matches_default_taxonomy_order() -> None:
    """Each position in ``DEFAULT_TAXONOMY`` must pin to the same
    (id, name, type) triple in migration 005's ``_DEFAULT_CATEGORIES``.

    IDs are assigned by 1-based position in insertion order: the first
    entry in ``DEFAULT_TAXONOMY`` becomes id=1, the second id=2, and so
    on.  This matches how ``seed_categories.py`` historically populated
    MySQL via auto-increment, so cross-service IDs agreed "by coincidence";
    this test makes that coincidence explicit and enforced.
    """
    seed_rows = _extract_default_categories()

    expected_rows = [
        (i + 1, name, data["type"].value)
        for i, (name, data) in enumerate(DEFAULT_TAXONOMY.items())
    ]

    assert seed_rows == expected_rows, (
        "Migration 005 _DEFAULT_CATEGORIES is out of sync with "
        "monolith DEFAULT_TAXONOMY.\n\n"
        f"Expected (from DEFAULT_TAXONOMY):\n  {expected_rows}\n\n"
        f"Actually in migration 005:\n  {seed_rows}\n\n"
        "Fix by updating whichever side was changed last so both "
        "agree on id, name, type, and position."
    )


def test_migration_005_ids_are_contiguous_from_one() -> None:
    """Defense against someone inserting a category in the middle of
    ``_DEFAULT_CATEGORIES`` with a gap in IDs — that would break the
    position-based pinning contract this migration relies on.
    """
    ids = [row[0] for row in _extract_default_categories()]
    expected = list(range(1, len(ids) + 1))
    assert ids == expected, (
        f"Migration 005 IDs must be contiguous starting at 1. "
        f"Got {ids}, expected {expected}."
    )


def test_default_taxonomy_types_are_supported_by_transaction_service() -> None:
    """Transaction-service's ``CategoryType`` enum must accept every
    type value used in ``DEFAULT_TAXONOMY``.  If someone adds a new
    type (e.g. ``loan``) in the monolith taxonomy without updating the
    enum, bank-sync would succeed locally but transaction-service would
    500 when hydrating categories (the bug that made this test
    necessary in the first place).
    """
    monolith_types = {data["type"].value for data in DEFAULT_TAXONOMY.values()}
    accepted_by_migration = {row[2] for row in _extract_default_categories()}

    unsupported = monolith_types - accepted_by_migration
    assert not unsupported, (
        f"DEFAULT_TAXONOMY uses category types not present in migration "
        f"005: {unsupported}. Extend _DEFAULT_CATEGORIES and the "
        "transaction-service ``CategoryType`` enum in lockstep."
    )
