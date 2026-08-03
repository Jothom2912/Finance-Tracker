from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from contracts.reclassification import (
    Disposition,
    ExecutionManifest,
    ExecutionRow,
    ReportRow,
    ServiceReport,
    SnapshotBoundary,
    authorize_execution,
    execution_manifest_bytes,
    load_execution_manifest,
    report_bytes,
)


def test_report_serialization_is_deterministic_and_rows_are_sorted() -> None:
    snapshot = SnapshotBoundary("2026-08-01T00:00:00Z", {"transactions": 2}, {})
    rows = (
        ReportRow("transaction", "2", 1, 1, Disposition.SAFE_ONE_TO_ONE, "direct_mapping", amount="2.00"),
        ReportRow("transaction", "1", 1, 1, Disposition.SAFE_ONE_TO_ONE, "direct_mapping", amount="1.00"),
    )
    report = ServiceReport("run-1", "transaction-service", "v1", "abc", snapshot, rows)

    assert report_bytes(report) == report_bytes(report)
    assert b'"source_id":"1"' in report_bytes(report)
    assert report.normalized().counts["safe_one_to_one"] == 2
    assert report.normalized().amounts["safe_one_to_one"] == "3.00"


def _manifest() -> ExecutionManifest:
    return ExecutionManifest(
        run_id="run-1",
        source_service="transaction-service",
        mapping_version="v1",
        mapping_sha256="mapping-hash",
        source_report_sha256="report-hash",
        rows=(
            ExecutionRow(
                "transaction",
                "1",
                7,
                30,
                Disposition.EVIDENCE_PROPOSAL,
                "constrained_rule_match",
                "investment",
                "018f0000-0000-7000-8000-000000000001",
            ),
        ),
    )


def test_execution_requires_hash_bound_explicit_approval(tmp_path: Path) -> None:
    manifest_path = tmp_path / "transaction-service.execution.json"
    manifest_path.write_bytes(execution_manifest_bytes(_manifest()))
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    approval = {
        "writes_authorized": True,
        "run_id": "run-1",
        "mapping_sha256": "mapping-hash",
        "summary_sha256": "summary-hash",
        "manifest_sha256": {"transaction-service": manifest_hash},
    }
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval, sort_keys=True, separators=(",", ":")) + "\n")
    approval_hash = hashlib.sha256(approval_path.read_bytes()).hexdigest()

    loaded = authorize_execution(
        manifest_path=manifest_path,
        approval_path=approval_path,
        expected_manifest_sha256=manifest_hash,
        expected_approval_sha256=approval_hash,
        expected_summary_sha256="summary-hash",
        expected_service="transaction-service",
    )
    assert loaded == _manifest()

    approval["writes_authorized"] = False
    approval_path.write_text(json.dumps(approval))
    rejected_hash = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="does not authorize"):
        authorize_execution(
            manifest_path=manifest_path,
            approval_path=approval_path,
            expected_manifest_sha256=manifest_hash,
            expected_approval_sha256=rejected_hash,
            expected_summary_sha256="summary-hash",
            expected_service="transaction-service",
        )


def test_execution_manifest_rejects_duplicate_identity(tmp_path: Path) -> None:
    manifest = _manifest()
    duplicate = ExecutionManifest(
        manifest.run_id,
        manifest.source_service,
        manifest.mapping_version,
        manifest.mapping_sha256,
        manifest.source_report_sha256,
        manifest.rows + manifest.rows,
    )
    path = tmp_path / "manifest.json"
    path.write_bytes(execution_manifest_bytes(duplicate))
    with pytest.raises(ValueError, match="duplicate"):
        load_execution_manifest(path, expected_service="transaction-service")
