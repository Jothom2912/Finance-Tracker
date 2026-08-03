"""Framework-free TAX-07 dry-run report contracts.

The contract deliberately contains no database or service imports.  Services emit one
deterministic shard each; the repository aggregator validates and combines those shards.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "tax07-report-v1"


class Disposition(StrEnum):
    SAFE_ONE_TO_ONE = "safe_one_to_one"
    EVIDENCE_PROPOSAL = "evidence_proposal"
    MANUAL_REVIEW = "manual_review"
    PROTECTED = "protected"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class SnapshotBoundary:
    captured_at: str
    table_counts: dict[str, int]
    reference_histograms: dict[str, dict[str, int]]
    outbox_max_id: int | str | None = None
    inbox_max_id: int | str | None = None


@dataclass(frozen=True, slots=True)
class ReportRow:
    source_kind: str
    source_id: str
    legacy_category_id: int | None
    legacy_subcategory_id: int | None
    disposition: Disposition
    reason_code: str
    target_key: str | None = None
    target_public_id: str | None = None
    amount: str | None = None
    changes_category_type: bool = False
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DetailManifest:
    filename: str
    sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class MappingTarget:
    key: str
    public_id: str


@dataclass(frozen=True, slots=True)
class MappingEntry:
    legacy_id: int
    disposition: Disposition
    reason_code: str
    targets: tuple[MappingTarget, ...]


@dataclass(frozen=True, slots=True)
class MappingRegistry:
    mapping_version: str
    taxonomy_version: str
    categories: tuple[MappingEntry, ...]
    subcategories: tuple[MappingEntry, ...]

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json(self.as_payload()))

    def as_payload(self) -> dict[str, object]:
        return asdict(self)

    def category(self, legacy_id: int) -> MappingEntry | None:
        return next((item for item in self.categories if item.legacy_id == legacy_id), None)

    def subcategory(self, legacy_id: int) -> MappingEntry | None:
        return next((item for item in self.subcategories if item.legacy_id == legacy_id), None)


@dataclass(frozen=True, slots=True)
class ServiceReport:
    run_id: str
    source_service: str
    mapping_version: str
    mapping_sha256: str
    snapshot: SnapshotBoundary
    rows: tuple[ReportRow, ...]
    schema_version: str = SCHEMA_VERSION
    detail: DetailManifest | None = None
    counts: dict[str, int] = field(default_factory=dict)
    amounts: dict[str, str] = field(default_factory=dict)

    def normalized(self) -> ServiceReport:
        rows = tuple(sorted(self.rows, key=lambda row: (row.source_kind, row.source_id)))
        counts = {item.value: 0 for item in Disposition}
        amounts = {item.value: "0.00" for item in Disposition}
        amount_totals = {item.value: Decimal("0") for item in Disposition}
        for row in rows:
            counts[row.disposition.value] += 1
            if row.amount is not None:
                amount_totals[row.disposition.value] += Decimal(row.amount)
        for key, value in amount_totals.items():
            amounts[key] = format(value, ".2f")
        return ServiceReport(
            run_id=self.run_id,
            source_service=self.source_service,
            mapping_version=self.mapping_version,
            mapping_sha256=self.mapping_sha256,
            snapshot=self.snapshot,
            rows=rows,
            schema_version=self.schema_version,
            detail=self.detail,
            counts=counts,
            amounts=amounts,
        )


@dataclass(frozen=True, slots=True)
class ExecutionRow:
    source_kind: str
    source_id: str
    legacy_category_id: int | None
    legacy_subcategory_id: int | None
    disposition: Disposition
    reason_code: str
    target_key: str
    target_public_id: str


@dataclass(frozen=True, slots=True)
class ExecutionManifest:
    run_id: str
    source_service: str
    mapping_version: str
    mapping_sha256: str
    source_report_sha256: str
    rows: tuple[ExecutionRow, ...]
    schema_version: str = "tax10-execution-v1"

    def normalized(self) -> ExecutionManifest:
        return ExecutionManifest(
            run_id=self.run_id,
            source_service=self.source_service,
            mapping_version=self.mapping_version,
            mapping_sha256=self.mapping_sha256,
            source_report_sha256=self.source_report_sha256,
            rows=tuple(sorted(self.rows, key=lambda row: (row.source_kind, row.source_id))),
            schema_version=self.schema_version,
        )


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def report_bytes(report: ServiceReport) -> bytes:
    return canonical_json(asdict(report.normalized()))


def write_report(report: ServiceReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report.source_service}.json"
    path.write_bytes(report_bytes(report))
    return path


def execution_manifest_bytes(manifest: ExecutionManifest) -> bytes:
    return canonical_json(asdict(manifest.normalized()))


def load_execution_manifest(path: Path, *, expected_service: str) -> ExecutionManifest:
    raw = json.loads(path.read_text())
    if raw.get("schema_version") != "tax10-execution-v1":
        raise ValueError("unsupported execution manifest schema")
    if raw.get("source_service") != expected_service:
        raise ValueError("execution manifest belongs to another service")
    rows = tuple(
        ExecutionRow(
            source_kind=str(row["source_kind"]),
            source_id=str(row["source_id"]),
            legacy_category_id=(int(row["legacy_category_id"]) if row.get("legacy_category_id") is not None else None),
            legacy_subcategory_id=(
                int(row["legacy_subcategory_id"]) if row.get("legacy_subcategory_id") is not None else None
            ),
            disposition=Disposition(row["disposition"]),
            reason_code=str(row["reason_code"]),
            target_key=str(row["target_key"]),
            target_public_id=str(row["target_public_id"]),
        )
        for row in raw["rows"]
    )
    manifest = ExecutionManifest(
        run_id=str(raw["run_id"]),
        source_service=str(raw["source_service"]),
        mapping_version=str(raw["mapping_version"]),
        mapping_sha256=str(raw["mapping_sha256"]),
        source_report_sha256=str(raw["source_report_sha256"]),
        rows=rows,
        schema_version=str(raw["schema_version"]),
    ).normalized()
    identities = [(row.source_kind, row.source_id) for row in manifest.rows]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate execution source identity")
    if any(
        row.disposition not in {Disposition.SAFE_ONE_TO_ONE, Disposition.EVIDENCE_PROPOSAL}
        or not row.reason_code
        or not row.target_key
        or not row.target_public_id
        for row in manifest.rows
    ):
        raise ValueError("execution manifest contains a non-executable row")
    return manifest


def authorize_execution(
    *,
    manifest_path: Path,
    approval_path: Path,
    expected_manifest_sha256: str,
    expected_approval_sha256: str,
    expected_summary_sha256: str,
    expected_service: str,
) -> ExecutionManifest:
    manifest_payload = manifest_path.read_bytes()
    approval_payload = approval_path.read_bytes()
    if sha256_bytes(manifest_payload) != expected_manifest_sha256:
        raise ValueError("execution manifest hash mismatch")
    if sha256_bytes(approval_payload) != expected_approval_sha256:
        raise ValueError("approval file hash mismatch")
    manifest = load_execution_manifest(manifest_path, expected_service=expected_service)
    approval = json.loads(approval_payload)
    if approval.get("writes_authorized") is not True:
        raise ValueError("approval does not authorize writes")
    if approval.get("summary_sha256") != expected_summary_sha256:
        raise ValueError("approval does not cover the supplied summary hash")
    approved_manifests = approval.get("manifest_sha256", {})
    if approved_manifests.get(expected_service) != expected_manifest_sha256:
        raise ValueError("approval does not cover this service manifest")
    if approval.get("run_id") != manifest.run_id or approval.get("mapping_sha256") != manifest.mapping_sha256:
        raise ValueError("approval boundary differs from execution manifest")
    return manifest


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_mapping(path: Path) -> MappingRegistry:
    raw = json.loads(path.read_text())

    def entries(name: str) -> tuple[MappingEntry, ...]:
        return tuple(
            MappingEntry(
                legacy_id=int(item["legacy_id"]),
                disposition=Disposition(item["disposition"]),
                reason_code=str(item["reason_code"]),
                targets=tuple(
                    MappingTarget(str(target["key"]), str(target["public_id"])) for target in item["targets"]
                ),
            )
            for item in raw[name]
        )

    registry = MappingRegistry(
        mapping_version=str(raw["mapping_version"]),
        taxonomy_version=str(raw["taxonomy_version"]),
        categories=entries("categories"),
        subcategories=entries("subcategories"),
    )
    if {item.legacy_id for item in registry.categories} != set(range(1, 11)):
        raise ValueError("mapping does not cover categories 1..10")
    if {item.legacy_id for item in registry.subcategories} != set(range(1, 42)):
        raise ValueError("mapping does not cover subcategories 1..41")
    return registry
