"""Read-only TAX-07 scanner for categorization-service-owned references."""

from __future__ import annotations

from collections import Counter

from contracts.reclassification import Disposition, ExecutionManifest, ReportRow, ServiceReport, SnapshotBoundary
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.reclassification import (
    CATEGORY_PROPOSALS,
    MAPPING_VERSION,
    SUBCATEGORY_PROPOSALS,
    mapping_sha256,
)
from app.domain.taxonomy_identity import TAXONOMY_PUBLIC_IDS
from app.models import (
    CategorizationResultModel,
    CategorizationRuleModel,
    CategoryModel,
    OutboxEventModel,
    ProcessedEventModel,
    SubCategoryModel,
)

_CATEGORIES = {item.legacy_id: item for item in CATEGORY_PROPOSALS}
_SUBCATEGORIES = {item.legacy_id: item for item in SUBCATEGORY_PROPOSALS}


async def apply_reclassification(
    session: AsyncSession,
    manifest: ExecutionManifest,
    *,
    execute: bool,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in manifest.rows:
        target = (
            await session.execute(
                select(SubCategoryModel).where(
                    SubCategoryModel.semantic_key == row.target_key,
                    SubCategoryModel.public_id == row.target_public_id,
                    SubCategoryModel.lifecycle == "active",
                )
            )
        ).scalar_one_or_none()
        if target is None:
            raise ValueError(f"active target identity not found: {row.target_key}")
        parent = await session.get(CategoryModel, target.category_id)
        if parent is None or parent.lifecycle != "active":
            raise ValueError(f"active parent not found for target: {row.target_key}")

        if row.source_kind == "categorization_result":
            result_model = await session.get(CategorizationResultModel, int(row.source_id))
            if result_model is None:
                counts["skipped_missing"] += 1
            elif result_model.tier.lower() in {"manual", "user", "gold"}:
                counts["skipped_protected"] += 1
            elif (result_model.category_id, result_model.subcategory_id) == (parent.id, target.id):
                counts["already_applied"] += 1
            elif (result_model.category_id, result_model.subcategory_id) != (
                row.legacy_category_id,
                row.legacy_subcategory_id,
            ):
                counts["skipped_changed"] += 1
            else:
                counts["validated" if not execute else "applied"] += 1
                if execute:
                    result_model.category_id = parent.id
                    result_model.subcategory_id = target.id
        elif row.source_kind == "system_rule":
            rule_model = await session.get(CategorizationRuleModel, int(row.source_id))
            if rule_model is None:
                counts["skipped_missing"] += 1
            elif rule_model.user_id is not None:
                counts["skipped_protected"] += 1
            elif rule_model.matches_subcategory_id == target.id:
                counts["already_applied"] += 1
            elif rule_model.matches_subcategory_id != row.legacy_subcategory_id:
                counts["skipped_changed"] += 1
            else:
                counts["validated" if not execute else "applied"] += 1
                if execute:
                    rule_model.matches_subcategory_id = target.id
        else:
            raise ValueError(f"unsupported categorization source kind: {row.source_kind}")
    if execute:
        await session.flush()
    return dict(sorted(counts.items()))


async def scan_categorization(
    session: AsyncSession,
    *,
    run_id: str,
    captured_at: str,
) -> ServiceReport:
    result_rows = list(
        (
            await session.execute(
                select(
                    CategorizationResultModel.id,
                    CategorizationResultModel.category_id,
                    CategorizationResultModel.subcategory_id,
                    CategorizationResultModel.tier,
                ).order_by(CategorizationResultModel.id)
            )
        ).all()
    )
    rule_rows = list(
        (
            await session.execute(
                select(
                    CategorizationRuleModel.id,
                    CategorizationRuleModel.user_id,
                    CategorizationRuleModel.matches_subcategory_id,
                ).order_by(CategorizationRuleModel.id)
            )
        ).all()
    )
    rows: list[ReportRow] = []
    histogram: Counter[str] = Counter()

    for result_id, category_id, subcategory_id, tier in result_rows:
        histogram[str(subcategory_id)] += 1
        proposal = _SUBCATEGORIES.get(subcategory_id)
        if proposal is None:
            continue
        protected = tier.lower() in {"manual", "user", "gold"}
        disposition = Disposition.PROTECTED if protected else proposal.disposition
        target = proposal.target_keys[0] if len(proposal.target_keys) == 1 and not protected else None
        rows.append(
            ReportRow(
                "categorization_result",
                str(result_id),
                category_id,
                subcategory_id,
                disposition,
                "manual_result_protected" if protected else proposal.reason_code,
                target,
                TAXONOMY_PUBLIC_IDS[target] if target else None,
            )
        )

    for rule_id, user_id, matches_subcategory_id in rule_rows:
        histogram[str(matches_subcategory_id)] += 1
        proposal = _SUBCATEGORIES.get(matches_subcategory_id)
        if proposal is None:
            continue
        protected = user_id is not None
        disposition = Disposition.PROTECTED if protected else proposal.disposition
        target = proposal.target_keys[0] if len(proposal.target_keys) == 1 and not protected else None
        rows.append(
            ReportRow(
                "user_or_learned_rule" if protected else "system_rule",
                str(rule_id),
                None,
                matches_subcategory_id,
                disposition,
                "user_rule_protected" if protected else proposal.reason_code,
                target,
                TAXONOMY_PUBLIC_IDS[target] if target else None,
            )
        )

    outbox_max = (await session.execute(select(func.max(OutboxEventModel.id)))).scalar_one()
    inbox_max = (await session.execute(select(func.max(ProcessedEventModel.id)))).scalar_one()
    snapshot = SnapshotBoundary(
        captured_at,
        {"categorization_results": len(result_rows), "categorization_rules": len(rule_rows)},
        {"subcategory_references": dict(sorted(histogram.items()))},
        str(outbox_max) if outbox_max is not None else None,
        int(inbox_max) if inbox_max is not None else None,
    )
    return ServiceReport(run_id, "categorization-service", MAPPING_VERSION, mapping_sha256(), snapshot, tuple(rows))
