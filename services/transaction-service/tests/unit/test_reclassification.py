from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.application.reclassification import (
    EvidenceResolution,
    _proposal_row,
    _resolve_evidence,
    apply_reclassification,
)
from app.models import CategoryModel, SubCategoryModel, TransactionModel
from contracts.reclassification import (
    Disposition,
    ExecutionManifest,
    ExecutionRow,
    MappingEntry,
    MappingRegistry,
    MappingTarget,
)


def _mapping() -> MappingRegistry:
    direct = {
        1: "groceries",
        20: "clothing_footwear",
        29: "investment",
        30: "cash_withdrawal",
    }
    evidence = {
        16: ("digital_services", "memberships"),
        20: ("sport_fitness", "clothing_footwear"),
        35: ("person_transfer", "refund"),
        37: ("own_accounts_savings", "unknown_transfer"),
        38: ("person_transfer", "unknown_transfer"),
        39: ("person_transfer", "unknown_transfer"),
        40: ("own_accounts_savings", "person_transfer", "unknown_transfer"),
        41: ("own_accounts_savings", "unknown_transfer"),
    }
    entries = []
    for legacy_id in range(1, 42):
        targets = evidence.get(legacy_id)
        if targets is not None:
            entries.append(
                MappingEntry(
                    legacy_id,
                    Disposition.EVIDENCE_PROPOSAL,
                    "split_leaf_requires_evidence",
                    tuple(MappingTarget(key, f"uuid-{key}") for key in targets),
                )
            )
        else:
            key = direct.get(legacy_id, f"leaf-{legacy_id}")
            entries.append(
                MappingEntry(
                    legacy_id,
                    Disposition.SAFE_ONE_TO_ONE,
                    "direct_leaf_mapping",
                    (MappingTarget(key, f"uuid-{key}"),),
                )
            )
    categories = tuple(
        MappingEntry(
            legacy_id,
            Disposition.SAFE_ONE_TO_ONE,
            "direct_parent_mapping",
            (MappingTarget(f"parent-{legacy_id}", f"uuid-parent-{legacy_id}"),),
        )
        for legacy_id in range(1, 11)
    )
    return MappingRegistry("v1", "taxonomy-v1", categories, tuple(entries))


@pytest.mark.parametrize("legacy_id", [16, 20, 35, 37, 38, 39, 40, 41])
def test_boundary_splits_remain_unresolved_without_structured_evidence(legacy_id: int) -> None:
    row = _proposal_row(
        source_kind="transaction",
        source_id=1,
        category_id=10,
        subcategory_id=legacy_id,
        amount=Decimal("100.00"),
        categorization_tier="rule",
        mapping=_mapping(),
    )
    assert row is not None
    assert row.disposition == Disposition.UNRESOLVED
    assert row.reason_code == "structured_evidence_missing_or_conflicting"
    assert row.target_key is None


@pytest.mark.parametrize(
    ("legacy_id", "target"),
    [(1, "groceries"), (29, "investment"), (30, "cash_withdrawal")],
)
def test_direct_mappings_are_safe_and_type_corrections_are_visible(legacy_id: int, target: str) -> None:
    row = _proposal_row(
        source_kind="transaction",
        source_id=1,
        category_id=7,
        subcategory_id=legacy_id,
        amount=Decimal("100.00"),
        categorization_tier="rule",
        mapping=_mapping(),
    )
    assert row is not None
    assert row.disposition == Disposition.SAFE_ONE_TO_ONE
    assert row.target_key == target
    assert row.changes_category_type is (legacy_id in {29, 30})


def test_manual_transaction_is_protected_even_for_direct_mapping() -> None:
    row = _proposal_row(
        source_kind="transaction",
        source_id=1,
        category_id=1,
        subcategory_id=1,
        amount=Decimal("10.00"),
        categorization_tier="manual",
        mapping=_mapping(),
    )
    assert row is not None
    assert row.disposition == Disposition.PROTECTED
    assert row.target_key is None


def test_active_taxonomy_reference_is_not_a_legacy_report_row() -> None:
    assert (
        _proposal_row(
            source_kind="transaction",
            source_id=1,
            category_id=13,
            subcategory_id=80,
            amount=Decimal("10.00"),
            categorization_tier="rule",
            mapping=_mapping(),
        )
        is None
    )


@pytest.mark.parametrize(
    ("legacy_id", "target", "direction"),
    [
        (16, "memberships", "outgoing"),
        (20, "sport_fitness", "outgoing"),
        (35, "refund", "incoming"),
        (37, "own_accounts_savings", "outgoing"),
        (38, "person_transfer", "outgoing"),
        (40, "own_accounts_savings", "incoming"),
    ],
)
def test_constrained_rule_evidence_selects_only_an_allowed_split_target(
    legacy_id: int, target: str, direction: str
) -> None:
    row = _proposal_row(
        source_kind="transaction",
        source_id=1,
        category_id=10,
        subcategory_id=legacy_id,
        amount=Decimal("100.00") if direction == "incoming" else Decimal("-100.00"),
        categorization_tier="rule",
        mapping=_mapping(),
        evidence_resolution=EvidenceResolution(
            target,
            "constrained_rule_match",
            (f"direction:{direction}", f"rule_target:{target}", "tier:rule", "confidence:high"),
        ),
    )
    assert row is not None
    assert row.disposition == Disposition.EVIDENCE_PROPOSAL
    assert row.reason_code == "constrained_rule_match"
    assert row.target_key == target
    assert row.evidence[0] == f"direction:{direction}"


def test_mobilepay_direction_without_matching_purpose_stays_unresolved() -> None:
    row = _proposal_row(
        source_kind="transaction",
        source_id=1,
        category_id=10,
        subcategory_id=40,
        amount=Decimal("-250.00"),
        categorization_tier="rule",
        mapping=_mapping(),
        evidence_resolution=EvidenceResolution(
            None,
            "structured_evidence_conflicting",
            ("direction:outgoing", "rule_target:shopping_unspecified", "tier:rule", "confidence:medium"),
        ),
    )
    assert row is not None
    assert row.disposition == Disposition.UNRESOLVED
    assert row.reason_code == "structured_evidence_conflicting"
    assert row.target_key is None


def test_manual_boundary_assignment_ignores_automated_evidence() -> None:
    row = _proposal_row(
        source_kind="transaction",
        source_id=1,
        category_id=10,
        subcategory_id=35,
        amount=Decimal("100.00"),
        categorization_tier="manual",
        mapping=_mapping(),
        evidence_resolution=EvidenceResolution("refund", "constrained_rule_match", ("tier:rule",)),
    )
    assert row is not None
    assert row.disposition == Disposition.PROTECTED
    assert row.target_key is None


@dataclass(frozen=True)
class _Result:
    subcategory_id: int = 109
    tier: str = "rule"
    confidence: str = "high"
    target_key: str | None = "memberships"


class _ChunkRecordingCategorizer:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def categorize_batch(self, items: list[dict]) -> list[_Result]:
        self.batch_sizes.append(len(items))
        return [_Result() for _ in items]


@pytest.mark.asyncio
async def test_evidence_requests_are_chunked_at_the_production_api_limit() -> None:
    models = [
        TransactionModel(
            id=index,
            user_id=1,
            account_id=1,
            account_name="Account",
            category_id=4,
            subcategory_id=16,
            amount=Decimal("-10.00"),
            transaction_type="expense",
            description="subscription",
            categorization_tier="rule",
        )
        for index in range(1, 502)
    ]
    categorizer = _ChunkRecordingCategorizer()
    resolutions = await _resolve_evidence(models, mapping=_mapping(), categorizer=categorizer)
    assert categorizer.batch_sizes == [500, 1]
    assert len(resolutions) == 501


class _WriterSession:
    def __init__(self, transaction: TransactionModel) -> None:
        self.transaction = transaction
        self.parent = CategoryModel(id=80, name="Formue", type="transfer", lifecycle="active")
        self.target = SubCategoryModel(
            id=180,
            name="Investering",
            category_id=80,
            public_id="target-public-id",
            semantic_key="investment",
            lifecycle="active",
        )
        self.added: list[object] = []

    async def execute(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: self.target)

    async def get(self, model: type[object], identity: int) -> object | None:
        if model is CategoryModel and identity == 80:
            return self.parent
        if model is TransactionModel and identity == 1:
            return self.transaction
        return None

    def add(self, model: object) -> None:
        self.added.append(model)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_writer_updates_names_and_emits_exactly_one_idempotent_outbox_event() -> None:
    transaction = TransactionModel(
        id=1,
        user_id=2,
        account_id=3,
        account_name="Konto",
        category_id=7,
        category_name="Finans",
        subcategory_id=29,
        subcategory_name="Legacy",
        amount=Decimal("100.00"),
        transaction_type="expense",
        description="sensitive",
        date=date(2026, 8, 1),
        categorization_tier="rule",
    )
    manifest = ExecutionManifest(
        "run-1",
        "transaction-service",
        "v1",
        "mapping-hash",
        "report-hash",
        (
            ExecutionRow(
                "transaction",
                "1",
                7,
                29,
                Disposition.SAFE_ONE_TO_ONE,
                "direct",
                "investment",
                "target-public-id",
            ),
        ),
    )
    session = _WriterSession(transaction)
    assert await apply_reclassification(session, manifest, execute=True) == {"applied": 1}
    assert (transaction.category_id, transaction.category_name) == (80, "Formue")
    assert (transaction.subcategory_id, transaction.subcategory_name) == (180, "Investering")
    assert len(session.added) == 1
    assert await apply_reclassification(session, manifest, execute=True) == {"already_applied": 1}
    assert len(session.added) == 1
