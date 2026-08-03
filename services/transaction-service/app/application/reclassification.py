"""Read-only TAX-07 scanner for transaction-service-owned references."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from contracts.events.transaction import TransactionUpdatedEvent
from contracts.reclassification import (
    Disposition,
    ExecutionManifest,
    MappingEntry,
    MappingRegistry,
    ReportRow,
    ServiceReport,
    SnapshotBoundary,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.outbox_adapter import TransactionOutboxAdapter
from app.domain.entities import direction_of
from app.models import (
    CategoryModel,
    OutboxEventModel,
    PlannedTransactionModel,
    ProcessedEventModel,
    SubCategoryModel,
    TransactionModel,
)

EVIDENCE_BATCH_SIZE = 500


@dataclass(frozen=True, slots=True)
class ResolvedTaxonomyTarget:
    subcategory_id: int
    subcategory_name: str
    subcategory_key: str
    subcategory_public_id: str
    category_id: int
    category_name: str
    category_type: str
    category_key: str
    category_public_id: str


class TaxonomyResolverPort(Protocol):
    async def resolve(self, semantic_key: str, public_id: str) -> ResolvedTaxonomyTarget | None: ...


async def apply_reclassification(
    session: AsyncSession,
    manifest: ExecutionManifest,
    *,
    execute: bool,
    taxonomy_resolver: TaxonomyResolverPort | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    outbox = TransactionOutboxAdapter(session)
    for row in manifest.rows:
        if row.source_kind != "transaction":
            raise ValueError(f"unsupported transaction source kind: {row.source_kind}")
        target = (
            await session.execute(
                select(SubCategoryModel).where(
                    SubCategoryModel.semantic_key == row.target_key,
                    SubCategoryModel.public_id == row.target_public_id,
                    SubCategoryModel.lifecycle == "active",
                )
            )
        ).scalar_one_or_none()
        if target is None and taxonomy_resolver is not None:
            resolved = await taxonomy_resolver.resolve(row.target_key, row.target_public_id)
            if resolved is not None:
                parent_copy = await session.get(CategoryModel, resolved.category_id)
                if parent_copy is None:
                    parent_copy = CategoryModel(
                        id=resolved.category_id,
                        name=resolved.category_name,
                        type=resolved.category_type,
                        public_id=resolved.category_public_id,
                        semantic_key=resolved.category_key,
                        lifecycle="active",
                    )
                    if execute:
                        session.add(parent_copy)
                elif (parent_copy.public_id, parent_copy.semantic_key) != (
                    resolved.category_public_id,
                    resolved.category_key,
                ):
                    raise ValueError(f"local category identity conflict: {resolved.category_key}")
                target = await session.get(SubCategoryModel, resolved.subcategory_id)
                if target is None:
                    target = SubCategoryModel(
                        id=resolved.subcategory_id,
                        name=resolved.subcategory_name,
                        category_id=resolved.category_id,
                        public_id=resolved.subcategory_public_id,
                        semantic_key=resolved.subcategory_key,
                        lifecycle="active",
                    )
                    if execute:
                        session.add(target)
                elif (target.public_id, target.semantic_key, target.category_id) != (
                    resolved.subcategory_public_id,
                    resolved.subcategory_key,
                    resolved.category_id,
                ):
                    raise ValueError(f"local subcategory identity conflict: {resolved.subcategory_key}")
        if target is None:
            raise ValueError(f"active target identity not found: {row.target_key}")
        parent = await session.get(CategoryModel, target.category_id)
        if parent is None or parent.lifecycle != "active":
            raise ValueError(f"active parent not found for target: {row.target_key}")
        model = await session.get(TransactionModel, int(row.source_id))
        if model is None or model.deleted_at is not None:
            counts["skipped_missing"] += 1
        elif (model.category_id, model.subcategory_id) == (parent.id, target.id):
            counts["already_applied"] += 1
        elif (model.categorization_tier or "").lower() in {"manual", "user", "gold"}:
            counts["skipped_protected"] += 1
        elif (model.category_id, model.subcategory_id) != (
            row.legacy_category_id,
            row.legacy_subcategory_id,
        ):
            counts["skipped_changed"] += 1
        else:
            counts["validated" if not execute else "applied"] += 1
            if execute:
                previous_category = model.category_name or ""
                model.category_id = parent.id
                model.category_name = parent.name
                model.subcategory_id = target.id
                model.subcategory_name = target.name
                await outbox.add(
                    event=TransactionUpdatedEvent(
                        transaction_id=model.id,
                        account_id=model.account_id,
                        user_id=model.user_id,
                        amount=str(model.amount),
                        previous_amount=str(model.amount),
                        transaction_type=model.transaction_type,
                        tx_date=model.date,
                        category_id=parent.id,
                        category=parent.name,
                        previous_category=previous_category,
                        description=model.description or "",
                        account_name=model.account_name,
                        subcategory_id=target.id,
                        categorization_tier=model.categorization_tier,
                        categorization_confidence=model.categorization_confidence,
                    ),
                    aggregate_type="transaction",
                    aggregate_id=str(model.id),
                )
    if execute:
        await session.flush()
    return dict(sorted(counts.items()))


class CategorizationResultPort(Protocol):
    @property
    def subcategory_id(self) -> int: ...

    @property
    def tier(self) -> str: ...

    @property
    def confidence(self) -> str: ...

    @property
    def target_key(self) -> str | None: ...


class EvidenceCategorizerPort(Protocol):
    async def categorize_batch(self, items: list[dict]) -> Sequence[CategorizationResultPort | None]: ...


@dataclass(frozen=True, slots=True)
class EvidenceResolution:
    target_key: str | None
    reason_code: str
    evidence: tuple[str, ...]


def _proposal_row(
    *,
    source_kind: str,
    source_id: int,
    category_id: int | None,
    subcategory_id: int | None,
    amount: Decimal,
    categorization_tier: str | None,
    mapping: MappingRegistry,
    evidence_resolution: EvidenceResolution | None = None,
) -> ReportRow | None:
    is_legacy_leaf = subcategory_id is not None and 1 <= subcategory_id <= 41
    is_legacy_parent = subcategory_id is None and category_id is not None and 1 <= category_id <= 10
    if not (is_legacy_leaf or is_legacy_parent):
        return None
    protected = categorization_tier is not None and categorization_tier.lower() in {"manual", "user", "gold"}
    proposal: MappingEntry | None = (
        mapping.subcategory(subcategory_id) if subcategory_id is not None else mapping.category(category_id or -1)
    )
    if protected:
        disposition = Disposition.PROTECTED
        reason = "manual_transaction_protected"
    elif proposal is None:
        disposition = Disposition.UNRESOLVED
        reason = "missing_or_target_taxonomy_reference"
    elif proposal.disposition == Disposition.EVIDENCE_PROPOSAL:
        target_by_key = {target.key: target for target in proposal.targets}
        evidence_target = evidence_resolution.target_key if evidence_resolution else None
        if evidence_resolution is not None and evidence_target in target_by_key:
            disposition = Disposition.EVIDENCE_PROPOSAL
            reason = evidence_resolution.reason_code
        else:
            disposition = Disposition.UNRESOLVED
            reason = (
                evidence_resolution.reason_code
                if evidence_resolution is not None
                else "structured_evidence_missing_or_conflicting"
            )
    else:
        disposition = proposal.disposition
        reason = proposal.reason_code
    target = None
    if proposal and len(proposal.targets) == 1 and disposition == Disposition.SAFE_ONE_TO_ONE:
        target = proposal.targets[0]
    elif proposal and disposition == Disposition.EVIDENCE_PROPOSAL and evidence_resolution is not None:
        target = next(
            (candidate for candidate in proposal.targets if candidate.key == evidence_resolution.target_key),
            None,
        )
    return ReportRow(
        source_kind,
        str(source_id),
        category_id,
        subcategory_id,
        disposition,
        reason,
        target.key if target else None,
        target.public_id if target else None,
        format(amount, ".2f"),
        bool(target and target.key in {"investment", "cash_withdrawal", "own_accounts_savings"}),
        evidence_resolution.evidence if evidence_resolution is not None else (),
    )


async def _resolve_evidence(
    transactions: list[TransactionModel],
    *,
    mapping: MappingRegistry,
    categorizer: EvidenceCategorizerPort | None,
) -> dict[int, EvidenceResolution]:
    candidates = [
        model
        for model in transactions
        if model.subcategory_id is not None
        and (proposal := mapping.subcategory(model.subcategory_id)) is not None
        and proposal.disposition == Disposition.EVIDENCE_PROPOSAL
        and model.categorization_tier not in {"manual", "user", "gold"}
    ]
    if not candidates or categorizer is None:
        return {}
    # Direction comes from transaction_type, not the sign of the stored amount:
    # the TAX-07 dry run derived both this call and its recorded direction
    # reason code from an unsigned amount, so every evidence row was resolved
    # as if incoming (TAX-14).
    inputs = [
        {
            "description": model.description or "",
            "amount": float(model.amount),
            "direction": direction_of(model.transaction_type),
        }
        for model in candidates
    ]
    results: list[CategorizationResultPort | None] = []
    for offset in range(0, len(inputs), EVIDENCE_BATCH_SIZE):
        results.extend(await categorizer.categorize_batch(inputs[offset : offset + EVIDENCE_BATCH_SIZE]))
    if len(results) != len(candidates):
        raise ValueError("categorization evidence result count mismatch")
    resolutions: dict[int, EvidenceResolution] = {}
    for model, result in zip(candidates, results, strict=True):
        direction = direction_of(model.transaction_type)
        if result is None:
            resolutions[model.id] = EvidenceResolution(
                None,
                "evidence_service_unavailable",
                (f"direction:{direction}", "categorization:no_result"),
            )
            continue
        target_key = result.target_key
        proposal = mapping.subcategory(model.subcategory_id or -1)
        allowed = {target.key for target in proposal.targets} if proposal is not None else set()
        matched = target_key in allowed and result.tier == "rule"
        resolutions[model.id] = EvidenceResolution(
            target_key if matched else None,
            "constrained_rule_match" if matched else "structured_evidence_conflicting",
            (
                f"direction:{direction}",
                f"rule_target:{target_key or 'unknown'}",
                f"tier:{result.tier}",
                f"confidence:{result.confidence}",
            ),
        )
    return resolutions


async def scan_transactions(
    session: AsyncSession,
    *,
    run_id: str,
    captured_at: str,
    mapping: MappingRegistry,
    evidence_categorizer: EvidenceCategorizerPort | None = None,
) -> ServiceReport:
    transactions = list(
        (
            await session.execute(
                select(TransactionModel).where(TransactionModel.deleted_at.is_(None)).order_by(TransactionModel.id)
            )
        ).scalars()
    )
    planned = list(
        (await session.execute(select(PlannedTransactionModel).order_by(PlannedTransactionModel.id))).scalars()
    )
    evidence = await _resolve_evidence(
        transactions,
        mapping=mapping,
        categorizer=evidence_categorizer,
    )
    proposed_rows = [
        _proposal_row(
            source_kind="transaction",
            source_id=model.id,
            category_id=model.category_id,
            subcategory_id=model.subcategory_id,
            amount=model.amount,
            categorization_tier=model.categorization_tier,
            mapping=mapping,
            evidence_resolution=evidence.get(model.id),
        )
        for model in transactions
    ] + [
        _proposal_row(
            source_kind="planned_transaction",
            source_id=model.id,
            category_id=model.category_id,
            subcategory_id=None,
            amount=model.amount,
            categorization_tier="user",
            mapping=mapping,
        )
        for model in planned
    ]
    rows = [row for row in proposed_rows if row is not None]
    category_histogram = Counter(str(model.category_id) for model in transactions + planned)
    subcategory_histogram = Counter(
        str(model.subcategory_id) for model in transactions if model.subcategory_id is not None
    )
    outbox_value = (await session.execute(select(func.max(OutboxEventModel.id)))).scalar_one()
    inbox_value = (await session.execute(select(func.max(ProcessedEventModel.id)))).scalar_one()
    outbox_max = str(outbox_value) if outbox_value is not None else None
    inbox_max = int(inbox_value) if inbox_value is not None else None
    snapshot = SnapshotBoundary(
        captured_at,
        {"transactions": len(transactions), "planned_transactions": len(planned)},
        {
            "category_references": dict(sorted(category_histogram.items())),
            "subcategory_references": dict(sorted(subcategory_histogram.items())),
        },
        outbox_max,
        inbox_max,
    )
    return ServiceReport(
        run_id,
        "transaction-service",
        mapping.mapping_version,
        mapping.sha256,
        snapshot,
        tuple(rows),
    )
