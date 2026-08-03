from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "tax07_reclassification.py"
SPEC = importlib.util.spec_from_file_location("tax07_reclassification", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MAPPING = json.dumps(
    {
        "mapping_version": "v1",
        "taxonomy_version": "taxonomy-v1",
        "categories": [
            {
                "legacy_id": 7,
                "targets": [{"key": "investment", "public_id": "018f0000-0000-7000-8000-000000000001"}],
            }
        ],
        "subcategories": [],
    },
    sort_keys=True,
).encode()
MAPPING_HASH = hashlib.sha256(MAPPING).hexdigest()


def _report(service: str) -> dict[str, object]:
    return {
        "schema_version": "tax07-report-v1",
        "run_id": "run-1",
        "source_service": service,
        "mapping_version": "v1",
        "mapping_sha256": MAPPING_HASH,
        "snapshot": {"captured_at": "2026-08-01T00:00:00Z", "table_counts": {}, "reference_histograms": {}},
        "rows": [],
    }


def test_aggregator_fails_closed_for_missing_or_mixed_shards(tmp_path: Path) -> None:
    (tmp_path / "taxonomy-mapping.json").write_bytes(MAPPING)
    (tmp_path / "categorization-service.json").write_text(json.dumps(_report("categorization-service")))
    with pytest.raises(ValueError, match="missing"):
        MODULE.aggregate(tmp_path)

    transaction = _report("transaction-service")
    transaction["mapping_version"] = "v2"
    (tmp_path / "transaction-service.json").write_text(json.dumps(transaction))
    (tmp_path / "budget-service.json").write_text(json.dumps(_report("budget-service")))
    with pytest.raises(ValueError, match="mixed mapping"):
        MODULE.aggregate(tmp_path)


def test_aggregator_emits_hashed_manifests_and_reconciles_analytics(tmp_path: Path) -> None:
    (tmp_path / "taxonomy-mapping.json").write_bytes(MAPPING)
    for service in ("categorization-service", "transaction-service", "budget-service"):
        report = _report(service)
        if service == "transaction-service":
            report["rows"] = [
                {
                    "source_kind": "transaction",
                    "source_id": "1",
                    "legacy_category_id": 7,
                    "disposition": "safe_one_to_one",
                    "reason_code": "direct_leaf_mapping",
                    "amount": "100.00",
                    "target_key": "investment",
                    "target_public_id": "018f0000-0000-7000-8000-000000000001",
                    "changes_category_type": True,
                }
            ]
        (tmp_path / f"{service}.json").write_text(json.dumps(report))

    baseline = {
        "hits": {"total": {"value": 1}},
        "aggregations": {"by_category": {"buckets": [{"key": 7, "doc_count": 1, "amount": {"value": 100.0}}]}},
    }
    summary = MODULE.aggregate(tmp_path, baseline)
    assert len(summary["detail_manifests"]) == 3
    assert summary["analytics"]["expense"]["delta"] == "-100.00"
    assert summary["analytics"]["investment"]["delta"] == "100.00"
    assert summary["analytics_traces"] == [
        {
            "from": "expense",
            "to": "investment",
            "disposition": "safe_one_to_one",
            "reason_code": "direct_leaf_mapping",
            "amount": "100.00",
        }
    ]
    assert summary["approval"]["writes_authorized"] is False
    assert summary["approval"]["proposed_write_scope"] == ["safe_one_to_one", "evidence_proposal"]
    assert "protected" in summary["approval"]["excluded_from_write_scope"]
    assert summary["execution_manifests"]["transaction-service"]["candidate_count"] == 1

    execution_dir = tmp_path / "execution"
    hashes = MODULE.write_execution_manifests(tmp_path, execution_dir)
    assert hashes["transaction-service"] == summary["execution_manifests"]["transaction-service"]["sha256"]
    manifest = json.loads((execution_dir / "transaction-service.execution.json").read_text())
    assert manifest["rows"][0]["target_key"] == "investment"


def test_execution_manifest_excludes_unresolved_targets_and_rejects_broadened_mapping(tmp_path: Path) -> None:
    (tmp_path / "taxonomy-mapping.json").write_bytes(MAPPING)
    for service in ("categorization-service", "transaction-service", "budget-service"):
        report = _report(service)
        if service == "categorization-service":
            report["rows"] = [
                {
                    "source_kind": "categorization_result",
                    "source_id": "1",
                    "legacy_category_id": 7,
                    "disposition": "evidence_proposal",
                    "reason_code": "split_requires_evidence",
                    "target_key": None,
                    "target_public_id": None,
                }
            ]
        (tmp_path / f"{service}.json").write_text(json.dumps(report))

    summary = MODULE.aggregate(tmp_path)
    item = summary["execution_manifests"]["categorization-service"]
    assert item["candidate_count"] == 0
    assert item["exclusions"] == {"target_not_resolved": 1}

    report = _report("transaction-service")
    report["rows"] = [
        {
            "source_kind": "transaction",
            "source_id": "9",
            "legacy_category_id": 7,
            "disposition": "safe_one_to_one",
            "reason_code": "direct",
            "target_key": "not-approved",
            "target_public_id": "018f0000-0000-7000-8000-000000000099",
        }
    ]
    (tmp_path / "transaction-service.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="outside approved mapping"):
        MODULE.aggregate(tmp_path)


def test_aggregator_fails_closed_for_analytics_projection_drift(tmp_path: Path) -> None:
    (tmp_path / "taxonomy-mapping.json").write_bytes(MAPPING)
    for service in ("categorization-service", "transaction-service", "budget-service"):
        report = _report(service)
        if service == "transaction-service":
            report["rows"] = [
                {
                    "source_kind": "transaction",
                    "source_id": "1",
                    "legacy_category_id": 1,
                    "disposition": "safe_one_to_one",
                    "reason_code": "direct_leaf_mapping",
                    "amount": "10.00",
                }
            ]
        (tmp_path / f"{service}.json").write_text(json.dumps(report))
    baseline = {
        "hits": {"total": {"value": 1}},
        "aggregations": {"by_category": {"buckets": [{"key": 1, "doc_count": 1, "amount": {"value": 20.0}}]}},
    }
    with pytest.raises(ValueError, match="analytics baseline does not reconcile"):
        MODULE.aggregate(tmp_path, baseline)


def test_aggregator_fails_closed_when_analytics_hit_count_excludes_source_rows(tmp_path: Path) -> None:
    (tmp_path / "taxonomy-mapping.json").write_bytes(MAPPING)
    for service in ("categorization-service", "transaction-service", "budget-service"):
        report = _report(service)
        if service == "transaction-service":
            report["rows"] = [
                {
                    "source_kind": "transaction",
                    "source_id": "1",
                    "legacy_category_id": 1,
                    "disposition": "safe_one_to_one",
                    "reason_code": "direct_leaf_mapping",
                    "amount": "10.00",
                }
            ]
        (tmp_path / f"{service}.json").write_text(json.dumps(report))
    baseline = {"hits": {"total": {"value": 0}}, "aggregations": {"by_category": {"buckets": []}}}
    with pytest.raises(ValueError, match="analytics baseline count differs"):
        MODULE.aggregate(tmp_path, baseline)
