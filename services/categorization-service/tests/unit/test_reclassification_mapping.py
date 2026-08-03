from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from app.application.reclassification import apply_reclassification
from app.domain.reclassification import (
    CATEGORY_PROPOSALS,
    MAPPING_VERSION,
    SUBCATEGORY_PROPOSALS,
    mapping_bytes,
    mapping_payload,
    mapping_sha256,
    validate_mapping,
)
from app.models import CategorizationResultModel, CategoryModel, SubCategoryModel
from contracts.reclassification import Disposition, ExecutionManifest, ExecutionRow


def test_mapping_covers_every_legacy_node_once_and_resolves_registry() -> None:
    validate_mapping()
    assert {item.legacy_id for item in CATEGORY_PROPOSALS} == set(range(1, 11))
    assert {item.legacy_id for item in SUBCATEGORY_PROPOSALS} == set(range(1, 42))


def test_splits_are_never_safe_and_mapping_is_identity_based() -> None:
    splits = [item for item in SUBCATEGORY_PROPOSALS if len(item.target_keys) > 1]
    assert splits
    assert all(item.disposition != Disposition.SAFE_ONE_TO_ONE for item in splits)
    payload = mapping_payload()
    assert "name" not in json.dumps(payload)
    assert mapping_bytes() == mapping_bytes()
    assert len(mapping_sha256()) == 64


class _Session:
    def __init__(self, result: CategorizationResultModel) -> None:
        self.result = result
        self.parent = CategoryModel(id=80, name="Formue", type="transfer", lifecycle="active")
        self.target = SubCategoryModel(
            id=180,
            name="Investering",
            category_id=80,
            public_id="target-public-id",
            semantic_key="investment",
            lifecycle="active",
        )
        self.flushes = 0

    async def execute(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: self.target)

    async def get(self, model: type[object], identity: int) -> object | None:
        if model is CategoryModel and identity == 80:
            return self.parent
        if model is CategorizationResultModel and identity == 1:
            return self.result
        return None

    async def flush(self) -> None:
        self.flushes += 1


def _execution_manifest() -> ExecutionManifest:
    return ExecutionManifest(
        "run-1",
        "categorization-service",
        MAPPING_VERSION,
        mapping_sha256(),
        "report-hash",
        (
            ExecutionRow(
                "categorization_result",
                "1",
                7,
                29,
                Disposition.SAFE_ONE_TO_ONE,
                "direct_leaf_mapping",
                "investment",
                "target-public-id",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_writer_is_idempotent_and_never_overwrites_manual_result() -> None:
    result = CategorizationResultModel(
        id=1,
        transaction_id=10,
        category_id=7,
        subcategory_id=29,
        tier="rule",
        confidence="high",
        model_version="rules-v1",
    )
    session = _Session(result)
    assert await apply_reclassification(session, _execution_manifest(), execute=True) == {"applied": 1}
    assert (result.category_id, result.subcategory_id) == (80, 180)
    assert await apply_reclassification(session, _execution_manifest(), execute=True) == {"already_applied": 1}

    result.category_id, result.subcategory_id, result.tier = 7, 29, "manual"
    assert await apply_reclassification(session, _execution_manifest(), execute=True) == {"skipped_protected": 1}
    assert (result.category_id, result.subcategory_id) == (7, 29)
