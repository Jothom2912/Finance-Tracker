"""Read-only TAX-07 scanner for budget-service-owned references."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from contracts.reclassification import (
    Disposition,
    ExecutionManifest,
    MappingRegistry,
    ReportRow,
    ServiceReport,
    SnapshotBoundary,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ICategoryPort
from app.models import BudgetLineModel, BudgetModel, MonthlyBudgetModel, OutboxEventModel


async def apply_reclassification(
    session: AsyncSession,
    manifest: ExecutionManifest,
    category_port: ICategoryPort,
    *,
    execute: bool,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    resolved: dict[tuple[str, str], int] = {}
    for row in manifest.rows:
        identity = (row.target_key, row.target_public_id)
        if identity not in resolved:
            target_id = await category_port.resolve_identity(*identity)
            if target_id is None:
                raise ValueError(f"active target identity not found: {row.target_key}")
            resolved[identity] = target_id
        target_id = resolved[identity]
        if row.source_kind == "legacy_budget":
            budget_model = await session.get(BudgetModel, int(row.source_id))
            if budget_model is None:
                counts["skipped_missing"] += 1
            elif budget_model.category_id == target_id:
                counts["already_applied"] += 1
            elif budget_model.category_id != row.legacy_category_id:
                counts["skipped_changed"] += 1
            else:
                counts["validated" if not execute else "applied"] += 1
                if execute:
                    budget_model.category_id = target_id
        elif row.source_kind == "monthly_budget_line":
            line_model = await session.get(BudgetLineModel, int(row.source_id))
            if line_model is None:
                counts["skipped_missing"] += 1
            elif line_model.category_id == target_id:
                counts["already_applied"] += 1
            elif line_model.category_id != row.legacy_category_id:
                counts["skipped_changed"] += 1
            else:
                collision = (
                    await session.execute(
                        select(BudgetLineModel.id).where(
                            BudgetLineModel.monthly_budget_id == line_model.monthly_budget_id,
                            BudgetLineModel.category_id == target_id,
                            BudgetLineModel.id != line_model.id,
                        )
                    )
                ).scalar_one_or_none()
                if collision is not None:
                    counts["skipped_collision"] += 1
                else:
                    counts["validated" if not execute else "applied"] += 1
                    if execute:
                        line_model.category_id = target_id
        else:
            raise ValueError(f"unsupported budget source kind: {row.source_kind}")
    if execute:
        await session.flush()
    return dict(sorted(counts.items()))


def _budget_row(
    source_kind: str,
    source_id: int,
    category_id: int,
    amount: Decimal,
    mapping: MappingRegistry,
) -> ReportRow | None:
    if not 1 <= category_id <= 10:
        return None
    proposal = mapping.category(category_id)
    if proposal is None:
        disposition = Disposition.UNRESOLVED
        reason = "missing_or_target_taxonomy_reference"
    else:
        disposition = proposal.disposition
        reason = proposal.reason_code
    target = (
        proposal.targets[0]
        if proposal and len(proposal.targets) == 1 and disposition == Disposition.SAFE_ONE_TO_ONE
        else None
    )
    return ReportRow(
        source_kind,
        str(source_id),
        category_id,
        None,
        disposition,
        reason,
        target.key if target else None,
        target.public_id if target else None,
        format(amount, ".2f"),
    )


async def scan_budgets(
    session: AsyncSession,
    *,
    run_id: str,
    captured_at: str,
    mapping: MappingRegistry,
) -> ServiceReport:
    budgets = list((await session.execute(select(BudgetModel).order_by(BudgetModel.id))).scalars())
    monthly = list((await session.execute(select(MonthlyBudgetModel).order_by(MonthlyBudgetModel.id))).scalars())
    lines = list((await session.execute(select(BudgetLineModel).order_by(BudgetLineModel.id))).scalars())
    proposed_rows = [
        _budget_row("legacy_budget", item.id, item.category_id, Decimal(item.amount), mapping) for item in budgets
    ] + [_budget_row("monthly_budget_line", item.id, item.category_id, Decimal(item.amount), mapping) for item in lines]

    rows = [row for row in proposed_rows if row is not None]
    collision_groups: dict[tuple[int, str], list[int]] = defaultdict(list)
    legacy_lines = [line for line in lines if 1 <= line.category_id <= 10]
    line_rows = [row for row in proposed_rows[len(budgets) :] if row is not None]
    for line, row in zip(legacy_lines, line_rows, strict=True):
        if row.target_key is not None:
            collision_groups[(line.monthly_budget_id, row.target_key)].append(line.id)
    collisions = {key: ids for key, ids in collision_groups.items() if len(ids) > 1}
    if collisions:
        rows = [
            ReportRow(
                row.source_kind,
                row.source_id,
                row.legacy_category_id,
                row.legacy_subcategory_id,
                Disposition.MANUAL_REVIEW,
                "budget_target_collision",
                row.target_key,
                row.target_public_id,
                row.amount,
            )
            if row.source_kind == "monthly_budget_line"
            and any(int(row.source_id) in ids for ids in collisions.values())
            else row
            for row in rows
        ]

    histogram = Counter(str(item.category_id) for item in budgets + lines)
    outbox_value = (await session.execute(select(func.max(OutboxEventModel.id)))).scalar_one()
    outbox_max = str(outbox_value) if outbox_value is not None else None
    snapshot = SnapshotBoundary(
        captured_at,
        {"budgets": len(budgets), "monthly_budgets": len(monthly), "budget_lines": len(lines)},
        {"category_references": dict(sorted(histogram.items()))},
        outbox_max,
        None,
    )
    return ServiceReport(run_id, "budget-service", mapping.mapping_version, mapping.sha256, snapshot, tuple(rows))
