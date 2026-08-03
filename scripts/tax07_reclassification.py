#!/usr/bin/env python3
"""Fail-closed aggregator for TAX-07 service-owned dry-run shards."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

EXPECTED_SERVICES = {"categorization-service", "transaction-service", "budget-service"}
SCHEMA_VERSION = "tax07-report-v1"
EXECUTION_SCHEMA_VERSION = "tax10-execution-v1"
WRITABLE_SOURCE_KINDS = {
    "categorization-service": {"categorization_result", "system_rule"},
    "transaction-service": {"transaction"},
    "budget-service": {"legacy_budget", "monthly_budget_line"},
}
TERMINAL_DISPOSITIONS = {
    "safe_one_to_one",
    "evidence_proposal",
    "manual_review",
    "protected",
    "unresolved",
}


def _load(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: report root must be an object")
    return value, hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _allowed_targets(mapping: dict[str, Any], row: dict[str, Any]) -> set[tuple[str, str]]:
    legacy_subcategory_id = row.get("legacy_subcategory_id")
    legacy_category_id = row.get("legacy_category_id")
    collection = "subcategories" if legacy_subcategory_id is not None else "categories"
    legacy_id = legacy_subcategory_id if legacy_subcategory_id is not None else legacy_category_id
    entry = next((item for item in mapping[collection] if item["legacy_id"] == legacy_id), None)
    if entry is None:
        return set()
    return {(str(target["key"]), str(target["public_id"])) for target in entry["targets"]}


def _execution_manifests(
    reports: dict[str, dict[str, Any]],
    report_hashes: dict[str, str],
    mapping: dict[str, Any],
) -> tuple[dict[str, bytes], dict[str, dict[str, object]]]:
    payloads: dict[str, bytes] = {}
    summaries: dict[str, dict[str, object]] = {}
    for service, report in sorted(reports.items()):
        candidates: list[dict[str, object]] = []
        exclusions: Counter[str] = Counter()
        identities: set[tuple[str, str]] = set()
        for row in report.get("rows", []):
            identity = (str(row.get("source_kind", "")), str(row.get("source_id", "")))
            if identity in identities:
                raise ValueError(f"duplicate source identity in {service}: {identity}")
            identities.add(identity)
            disposition = str(row.get("disposition", ""))
            target_key = row.get("target_key")
            target_public_id = row.get("target_public_id")
            if identity[0] not in WRITABLE_SOURCE_KINDS[service]:
                exclusions["source_kind_not_writable"] += 1
                continue
            if disposition not in {"safe_one_to_one", "evidence_proposal"}:
                exclusions[f"disposition:{disposition}"] += 1
                continue
            if not target_key or not target_public_id:
                exclusions["target_not_resolved"] += 1
                continue
            target_pair = (str(target_key), str(target_public_id))
            if target_pair not in _allowed_targets(mapping, row):
                raise ValueError(f"target outside approved mapping for {service} {identity}")
            candidates.append(
                {
                    "source_kind": identity[0],
                    "source_id": identity[1],
                    "legacy_category_id": row.get("legacy_category_id"),
                    "legacy_subcategory_id": row.get("legacy_subcategory_id"),
                    "disposition": disposition,
                    "reason_code": str(row["reason_code"]),
                    "target_key": target_pair[0],
                    "target_public_id": target_pair[1],
                }
            )
        manifest = {
            "schema_version": EXECUTION_SCHEMA_VERSION,
            "run_id": report["run_id"],
            "source_service": service,
            "mapping_version": report["mapping_version"],
            "mapping_sha256": report["mapping_sha256"],
            "source_report_sha256": report_hashes[service],
            "rows": sorted(candidates, key=lambda row: (str(row["source_kind"]), str(row["source_id"]))),
        }
        payload = _canonical_bytes(manifest)
        payloads[service] = payload
        summaries[service] = {
            "candidate_count": len(candidates),
            "excluded_count": sum(exclusions.values()),
            "exclusions": dict(sorted(exclusions.items())),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    return payloads, summaries


def _validate_analytics_baseline(transaction_rows: list[dict[str, Any]], baseline: dict[str, Any]) -> None:
    hits = int(baseline["hits"]["total"]["value"])
    buckets = {int(item["key"]): item for item in baseline["aggregations"]["by_category"]["buckets"]}
    source_rows = [row for row in transaction_rows if row.get("source_kind") == "transaction"]
    if hits != len(source_rows):
        raise ValueError(f"analytics baseline count differs from source: source={len(source_rows)}, analytics={hits}")
    source_counts: Counter[int] = Counter(int(row["legacy_category_id"]) for row in source_rows)
    source_amounts: Counter[int] = Counter()
    for row in source_rows:
        source_amounts[int(row["legacy_category_id"])] += Decimal(str(row["amount"]))
    differences: list[str] = []
    for category_id in range(1, 11):
        bucket = buckets.get(category_id, {"doc_count": 0, "amount": {"value": 0}})
        es_count = int(bucket["doc_count"])
        es_amount = Decimal(str(bucket["amount"]["value"])).quantize(Decimal("0.01"))
        if source_counts[category_id] != es_count or source_amounts[category_id] != es_amount:
            differences.append(
                f"category {category_id}: source={source_counts[category_id]}/{source_amounts[category_id]:.2f}, "
                f"analytics={es_count}/{es_amount:.2f}"
            )
    if differences:
        raise ValueError(f"analytics baseline does not reconcile ({hits} active documents): " + "; ".join(differences))


def aggregate(input_dir: Path, analytics_baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    mapping_path = input_dir / "taxonomy-mapping.json"
    if not mapping_path.is_file():
        raise ValueError("missing taxonomy-mapping.json")
    mapping_bytes = mapping_path.read_bytes()
    mapping_digest = hashlib.sha256(mapping_bytes).hexdigest()
    mapping = json.loads(mapping_bytes)
    reports: dict[str, dict[str, Any]] = {}
    report_hashes: dict[str, str] = {}
    manifests: list[dict[str, object]] = []
    for path in sorted(input_dir.glob("*-service.json")):
        report, digest = _load(path)
        service = str(report.get("source_service", ""))
        if service in reports:
            raise ValueError(f"duplicate source shard: {service}")
        reports[service] = report
        report_hashes[service] = digest
        manifests.append({"filename": path.name, "sha256": digest, "row_count": len(report.get("rows", []))})
    missing = EXPECTED_SERVICES - set(reports)
    extra = set(reports) - EXPECTED_SERVICES
    if missing or extra:
        raise ValueError(f"service shard mismatch; missing={sorted(missing)}, extra={sorted(extra)}")

    schema_versions = {str(report.get("schema_version")) for report in reports.values()}
    mapping_versions = {str(report.get("mapping_version")) for report in reports.values()}
    mapping_hashes = {str(report.get("mapping_sha256")) for report in reports.values()}
    run_ids = {str(report.get("run_id")) for report in reports.values()}
    captured_at = {str(report.get("snapshot", {}).get("captured_at")) for report in reports.values()}
    if schema_versions != {SCHEMA_VERSION}:
        raise ValueError(f"mixed or unsupported schema versions: {sorted(schema_versions)}")
    if len(mapping_versions) != 1 or len(mapping_hashes) != 1:
        raise ValueError("mixed mapping versions or hashes")
    if mapping_hashes != {mapping_digest}:
        raise ValueError("invalid mapping hash")
    if len(run_ids) != 1 or len(captured_at) != 1:
        raise ValueError("mixed run IDs or snapshot boundaries")

    counts: Counter[str] = Counter()
    amounts: Counter[str] = Counter()
    analytics_before: Counter[str] = Counter()
    analytics_after: Counter[str] = Counter()
    analytics_traces: Counter[tuple[str, str, str, str]] = Counter()
    transaction_rows = reports["transaction-service"].get("rows", [])
    if analytics_baseline is not None:
        _validate_analytics_baseline(transaction_rows, analytics_baseline)
    for report in reports.values():
        for row in report.get("rows", []):
            disposition = str(row.get("disposition", ""))
            reason = str(row.get("reason_code", ""))
            if disposition not in TERMINAL_DISPOSITIONS or not reason:
                raise ValueError("non-terminal or unexplained report row")
            counts[disposition] += 1
            if row.get("amount") is not None:
                amounts[disposition] += Decimal(str(row["amount"]))

    special_targets = {
        "investment": "investment",
        "cash_withdrawal": "cash",
        "own_accounts_savings": "savings",
        "unknown_transfer": "unknown_transfer",
        "person_transfer": "unknown_transfer",
    }
    for row in transaction_rows:
        if row.get("source_kind") != "transaction" or row.get("amount") is None:
            continue
        amount = Decimal(str(row["amount"]))
        legacy_category = row.get("legacy_category_id")
        before_group = (
            "expense" if legacy_category in range(1, 9) else "income" if legacy_category == 9 else "own_account"
        )
        analytics_before[before_group] += amount
        target = row.get("target_key")
        if target in special_targets:
            after_group = special_targets[target]
        elif row.get("changes_category_type"):
            after_group = "own_account"
        else:
            after_group = before_group
        analytics_after[after_group] += amount
        if before_group != after_group:
            reason = str(row.get("reason_code", ""))
            disposition = str(row.get("disposition", ""))
            if not reason or not target:
                raise ValueError("analytics delta lacks a traced proposal/reason")
            analytics_traces[(before_group, after_group, disposition, reason)] += amount

    analytics_groups = ("expense", "income", "investment", "cash", "savings", "own_account", "unknown_transfer")
    analytics = {
        group: {
            "before": format(analytics_before[group], ".2f"),
            "after": format(analytics_after[group], ".2f"),
            "delta": format(analytics_after[group] - analytics_before[group], ".2f"),
        }
        for group in analytics_groups
    }
    if sum(analytics_before.values(), Decimal()) != sum(analytics_after.values(), Decimal()):
        raise ValueError("analytics source totals do not reconcile")

    snapshots = {service: report["snapshot"] for service, report in sorted(reports.items())}
    _, execution_summaries = _execution_manifests(reports, report_hashes, mapping)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": next(iter(run_ids)),
        "mapping_version": next(iter(mapping_versions)),
        "mapping_sha256": next(iter(mapping_hashes)),
        "captured_at": next(iter(captured_at)),
        "counts": dict(sorted(counts.items())),
        "amounts": {key: format(value, ".2f") for key, value in sorted(amounts.items())},
        "analytics": analytics,
        "analytics_traces": [
            {
                "from": before,
                "to": after,
                "disposition": disposition,
                "reason_code": reason,
                "amount": format(amount, ".2f"),
            }
            for (before, after, disposition, reason), amount in sorted(analytics_traces.items())
        ],
        "approval": {
            "status": "owner_review_required",
            "writes_authorized": False,
            "proposed_write_scope": ["safe_one_to_one", "evidence_proposal"],
            "excluded_from_write_scope": ["manual_review", "protected", "unresolved"],
            "conflict_policy": "re-read source version; skip changed, deleted, protected or no-longer-matching rows",
            "recovery_design": "restore from the fresh pre-write snapshot or forward-repair through service-owned APIs/events",
            "operator_checklist": [
                "obtain product/owner approval for this exact summary hash",
                "create and verify a fresh pre-write snapshot",
                "re-run all scanners and require identical mapping and source hashes",
                "execute only through service-owned write paths under a separately approved plan",
                "reconcile databases, outbox/inbox and Elasticsearch after execution",
            ],
        },
        "snapshots": snapshots,
        "detail_manifests": manifests,
        "execution_manifests": execution_summaries,
    }


def write_execution_manifests(input_dir: Path, output_dir: Path) -> dict[str, str]:
    mapping_path = input_dir / "taxonomy-mapping.json"
    mapping_bytes = mapping_path.read_bytes()
    mapping_digest = hashlib.sha256(mapping_bytes).hexdigest()
    mapping = json.loads(mapping_bytes)
    reports: dict[str, dict[str, Any]] = {}
    report_hashes: dict[str, str] = {}
    for path in sorted(input_dir.glob("*-service.json")):
        report, digest = _load(path)
        service = str(report.get("source_service", ""))
        if report.get("mapping_sha256") != mapping_digest:
            raise ValueError("invalid mapping hash")
        reports[service] = report
        report_hashes[service] = digest
    if set(reports) != EXPECTED_SERVICES:
        raise ValueError("service shard mismatch while writing execution manifests")
    payloads, _ = _execution_manifests(reports, report_hashes, mapping)
    output_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for service, payload in payloads.items():
        path = output_dir / f"{service}.execution.json"
        path.write_bytes(payload)
        hashes[service] = hashlib.sha256(payload).hexdigest()
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate three TAX-07 dry-run shards")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--analytics-baseline", required=True, help="Raw Elasticsearch aggregation response")
    parser.add_argument("--execution-dir", help="Write TAX-10 per-service candidate manifests")
    args = parser.parse_args()
    baseline = json.loads(Path(args.analytics_baseline).read_text())
    summary = aggregate(Path(args.input_dir), baseline)
    if args.execution_dir:
        written_hashes = write_execution_manifests(Path(args.input_dir), Path(args.execution_dir))
        expected_hashes = {service: item["sha256"] for service, item in summary["execution_manifests"].items()}
        if written_hashes != expected_hashes:
            raise ValueError("written execution manifest hashes differ from approval summary")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
