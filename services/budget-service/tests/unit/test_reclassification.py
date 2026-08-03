from __future__ import annotations

import os
from decimal import Decimal
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.application.reclassification import _budget_row, apply_reclassification  # noqa: E402
from app.models import BudgetLineModel, BudgetModel  # noqa: E402
from contracts.reclassification import (  # noqa: E402
    Disposition,
    ExecutionManifest,
    ExecutionRow,
    MappingEntry,
    MappingRegistry,
    MappingTarget,
)


def test_split_parent_budget_is_reviewed_without_apportionment() -> None:
    mapping = MappingRegistry(
        "v1",
        "taxonomy-v1",
        (
            MappingEntry(
                5,
                Disposition.MANUAL_REVIEW,
                "split_parent_requires_child",
                (MappingTarget("shopping", "uuid-shopping"), MappingTarget("health", "uuid-health")),
            ),
        ),
        (),
    )
    row = _budget_row("legacy_budget", 1, 5, Decimal("500.00"), mapping)
    assert row is not None
    assert row.disposition == Disposition.MANUAL_REVIEW
    assert row.target_key is None
    assert row.amount == "500.00"


def test_active_taxonomy_budget_is_not_a_legacy_report_row() -> None:
    mapping = MappingRegistry("v1", "taxonomy-v1", (), ())
    assert _budget_row("legacy_budget", 1, 13, Decimal("500.00"), mapping) is None


class _CategoryPort:
    async def resolve_identity(self, semantic_key: str, public_id: str) -> int | None:
        return 80 if (semantic_key, public_id) == ("food_drink", "target-public-id") else None


class _BudgetSession:
    def __init__(self, line: BudgetLineModel, *, collision: bool = False) -> None:
        self.line = line
        self.collision = collision

    async def get(self, model: type[object], identity: int) -> object | None:
        if model is BudgetLineModel and identity == 1:
            return self.line
        if model is BudgetModel:
            return None
        return None

    async def execute(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: 2 if self.collision else None)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_budget_writer_skips_collision_and_is_idempotent() -> None:
    line = BudgetLineModel(id=1, monthly_budget_id=10, category_id=1, amount=Decimal("500.00"))
    manifest = ExecutionManifest(
        "run-1",
        "budget-service",
        "v1",
        "mapping-hash",
        "report-hash",
        (
            ExecutionRow(
                "monthly_budget_line",
                "1",
                1,
                None,
                Disposition.SAFE_ONE_TO_ONE,
                "direct",
                "food_drink",
                "target-public-id",
            ),
        ),
    )
    assert await apply_reclassification(
        _BudgetSession(line, collision=True), manifest, _CategoryPort(), execute=True
    ) == {"skipped_collision": 1}
    assert line.category_id == 1

    session = _BudgetSession(line)
    assert await apply_reclassification(session, manifest, _CategoryPort(), execute=True) == {"applied": 1}
    assert line.category_id == 80
    assert await apply_reclassification(session, manifest, _CategoryPort(), execute=True) == {"already_applied": 1}
