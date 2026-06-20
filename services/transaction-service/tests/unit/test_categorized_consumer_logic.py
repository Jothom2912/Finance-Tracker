"""Unit tests for the categorization-apply logic (Fase 2).

These exercise the pure decision logic of
``TransactionCategorizedConsumer._apply_categorization`` without a database:
the parent name is resolved by the caller and passed in, so the method only
manipulates in-memory ``TransactionModel`` attributes.

Invariants under test:
- ``category_name`` always ends up as the PARENT name (never the sub-name).
- the sub-level name from the event lands in ``subcategory_name``.
- a manual user choice (tier == "manual") is never overwritten.
"""

from __future__ import annotations

from app.models import TransactionModel
from app.workers.categorized_consumer import TransactionCategorizedConsumer

apply = TransactionCategorizedConsumer._apply_categorization


def _event(**overrides: object) -> dict:
    base = {
        "event_type": "transaction.categorized",
        "transaction_id": 1,
        "category_id": 1,
        "subcategory_id": 1,
        "subcategory_name": "Dagligvarer",
        "tier": "rule",
        "confidence": "high",
    }
    base.update(overrides)
    return base


def test_category_name_is_parent_subcategory_name_is_sub() -> None:
    tx = TransactionModel(id=1, category_id=None, category_name=None, subcategory_name=None)

    apply(tx, _event(), parent_name="Mad & drikke")

    assert tx.category_name == "Mad & drikke"  # parent, not "Dagligvarer"
    assert tx.subcategory_name == "Dagligvarer"
    assert tx.subcategory_id == 1
    assert tx.category_id == 1
    assert tx.categorization_tier == "rule"


def test_does_not_write_subcategory_name_into_category_name() -> None:
    """Regression guard for the old bug (category_name = subcategory_name)."""
    tx = TransactionModel(id=1, category_id=1, category_name="Mad & drikke", subcategory_name=None)

    apply(tx, _event(), parent_name="Mad & drikke")

    assert tx.category_name == "Mad & drikke"
    assert tx.category_name != tx.subcategory_name


def test_manual_choice_is_not_overwritten() -> None:
    tx = TransactionModel(
        id=1,
        category_id=2,
        category_name="Bolig",
        subcategory_name=None,
        subcategory_id=6,
        categorization_tier="manual",
        categorization_confidence="high",
    )

    # An auto event pointing at a different category must be ignored.
    apply(tx, _event(category_id=1, subcategory_id=1), parent_name="Mad & drikke")

    assert tx.category_name == "Bolig"
    assert tx.category_id == 2
    assert tx.subcategory_id == 6
    assert tx.categorization_tier == "manual"


def test_category_name_left_untouched_when_parent_unknown() -> None:
    """If the parent name can't be resolved, keep the existing category_name."""
    tx = TransactionModel(id=1, category_id=1, category_name="Mad & drikke", subcategory_name=None)

    apply(tx, _event(), parent_name=None)

    assert tx.category_name == "Mad & drikke"
    assert tx.subcategory_name == "Dagligvarer"


def test_noop_when_already_consistent() -> None:
    tx = TransactionModel(
        id=1,
        category_id=1,
        category_name="Mad & drikke",
        subcategory_id=1,
        subcategory_name="Dagligvarer",
        categorization_tier="rule",
        categorization_confidence="high",
    )

    apply(tx, _event(), parent_name="Mad & drikke")

    # Nothing changed (idempotent re-application).
    assert tx.category_name == "Mad & drikke"
    assert tx.subcategory_name == "Dagligvarer"
    assert tx.categorization_tier == "rule"
