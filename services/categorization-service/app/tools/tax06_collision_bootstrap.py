"""Install TAX-06 from revision 007 when migration 008's fixed IDs collide.

This is an exceptional, operator-gated bridge for P2-44. Normal databases use
Alembic directly. The command owns one transaction and stamps revision 008 only
after the complete canonical state has been validated.

Usage: ``python -m app.tools.tax06_collision_bootstrap --run-id <change-id>``
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, Engine, create_engine

from app.domain.seed_contracts import CategorizationRuleSeed, MerchantSeed, TaxonomyDefinition

_CATEGORY_FLOOR = 24
_SUBCATEGORY_FLOOR = 109
_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_008 = _SERVICE_ROOT / "migrations" / "versions" / "008_activate_taxonomy_v1.py"


def collision_free_start(maximum_id: int | None, sequence_value: int | None, floor: int) -> int:
    """Return the first ID above occupied, sequence-reserved and published ranges."""
    return max(maximum_id or 0, sequence_value or 0, floor - 1) + 1


def allocate_surrogates(keys: Sequence[str], start: int) -> dict[str, int]:
    return {key: start + offset for offset, key in enumerate(keys)}


def bootstrap(engine: Engine, run_id: str) -> tuple[int, int]:
    if not run_id.strip():
        raise ValueError("run ID must not be empty")
    migration = _load_migration_008()
    with engine.begin() as connection:
        connection.execute(sa.text("SELECT pg_advisory_xact_lock(244008)"))
        revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision in {"008", "009"}:
            return _existing_allocation_start(connection, run_id)
        if revision != "007":
            raise RuntimeError(f"P2-44 bootstrap requires revision 007, found {revision}")

        connection.execute(sa.text("LOCK TABLE categories, subcategories IN ACCESS EXCLUSIVE MODE"))
        definitions, public_ids, taxonomy_version, merchants, rules = migration._load_snapshot()
        parent_keys = [item.semantic_key for item in definitions if item.parent_key is None]
        child_keys = [item.semantic_key for item in definitions if item.parent_key is not None]
        category_start = _next_start(connection, "categories", "categories_id_seq", _CATEGORY_FLOOR)
        subcategory_start = _next_start(connection, "subcategories", "subcategories_id_seq", _SUBCATEGORY_FLOOR)
        parent_ids = allocate_surrogates(parent_keys, category_start)
        child_ids = allocate_surrogates(child_keys, subcategory_start)

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration._add_schema()
        _create_ledger(connection)
        _seed_target(
            connection,
            migration,
            definitions,
            public_ids,
            taxonomy_version,
            merchants,
            rules,
            parent_ids,
            child_ids,
        )
        _record_allocations(connection, run_id, public_ids, parent_ids, child_ids)
        _validate_postconditions(connection, public_ids, parent_ids, child_ids)
        connection.execute(sa.text("UPDATE alembic_version SET version_num='008' WHERE version_num='007'"))
    return category_start, subcategory_start


def _existing_allocation_start(connection: Connection, run_id: str) -> tuple[int, int]:
    ledger_exists = connection.execute(
        sa.text("SELECT to_regclass('taxonomy_surrogate_allocations') IS NOT NULL")
    ).scalar_one()
    if not ledger_exists:
        raise RuntimeError("revision is already TAX-06 but its surrogate allocation ledger is missing")
    run_ids = set(
        connection.execute(sa.text("SELECT DISTINCT bootstrap_run_id FROM taxonomy_surrogate_allocations")).scalars()
    )
    if run_ids != {run_id}:
        raise RuntimeError(f"run ID does not own existing allocation ledger: {sorted(run_ids)}")
    rows = connection.execute(
        sa.text("SELECT node_kind,MIN(surrogate_id),COUNT(*) FROM taxonomy_surrogate_allocations GROUP BY node_kind")
    ).all()
    allocations = {kind: (minimum, count) for kind, minimum, count in rows}
    if allocations.get("category", (None, 0))[1] != 13 or allocations.get("subcategory", (None, 0))[1] != 67:
        raise RuntimeError("existing surrogate allocation ledger is incomplete")
    return allocations["category"][0], allocations["subcategory"][0]


def _load_migration_008() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tax06_migration_008", _MIGRATION_008)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_MIGRATION_008}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _next_start(connection: Connection, table: str, sequence: str, floor: int) -> int:
    maximum = connection.execute(sa.text(f"SELECT MAX(id) FROM {table}")).scalar_one()
    sequence_value = connection.execute(sa.text(f"SELECT last_value FROM {sequence}")).scalar_one()
    return collision_free_start(maximum, sequence_value, floor)


def _create_ledger(connection: Connection) -> None:
    connection.execute(
        sa.text(
            "CREATE TABLE taxonomy_surrogate_allocations ("
            "node_kind VARCHAR(20) NOT NULL, semantic_key VARCHAR(100) NOT NULL, "
            "public_id VARCHAR(36) NOT NULL, surrogate_id INTEGER NOT NULL, "
            "bootstrap_run_id VARCHAR(100) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
            "CONSTRAINT pk_taxonomy_surrogate_allocations PRIMARY KEY (node_kind, semantic_key), "
            "CONSTRAINT uq_taxonomy_allocation_public_id UNIQUE (public_id), "
            "CONSTRAINT uq_taxonomy_allocation_surrogate UNIQUE (node_kind, surrogate_id))"
        )
    )


def _seed_target(
    connection: Connection,
    migration: ModuleType,
    definitions: Sequence[TaxonomyDefinition],
    public_ids: Mapping[str, str],
    taxonomy_version: int,
    merchants: Sequence[MerchantSeed],
    rules: Sequence[CategorizationRuleSeed],
    parent_ids: Mapping[str, int],
    child_ids: Mapping[str, int],
) -> None:
    connection.execute(
        sa.text("UPDATE categories SET lifecycle='deprecated', deprecated_in_version=1 WHERE semantic_key IS NULL")
    )
    connection.execute(
        sa.text("UPDATE subcategories SET lifecycle='deprecated', deprecated_in_version=1 WHERE semantic_key IS NULL")
    )
    child_order: dict[str, int] = {}
    for definition in definitions:
        key = definition.semantic_key
        if definition.parent_key is None:
            connection.execute(
                sa.text(
                    "INSERT INTO categories (id,name,type,display_order,public_id,semantic_key,description,"
                    "taxonomy_version,lifecycle) VALUES "
                    "(:id,:name,:type,:display_order,:public_id,:key,:description,1,'active')"
                ),
                {
                    "id": parent_ids[key],
                    "name": definition.display_name,
                    "type": definition.category_type.value,
                    "display_order": list(parent_ids).index(key) + 1,
                    "public_id": public_ids[key],
                    "key": key,
                    "description": definition.description,
                },
            )
            continue
        child_order[definition.parent_key] = child_order.get(definition.parent_key, 0) + 1
        connection.execute(
            sa.text(
                "INSERT INTO subcategories (id,name,category_id,is_default,public_id,semantic_key,description,"
                "is_fallback,taxonomy_version,lifecycle) VALUES "
                "(:id,:name,:category_id,true,:public_id,:key,:description,:is_fallback,1,'active')"
            ),
            {
                "id": child_ids[key],
                "name": definition.display_name,
                "category_id": parent_ids[definition.parent_key],
                "public_id": public_ids[key],
                "key": key,
                "description": definition.description,
                "is_fallback": definition.is_fallback,
            },
        )

    merchant_ids: dict[str, int] = {}
    for merchant in merchants:
        merchant_id = connection.execute(
            sa.text(
                "INSERT INTO merchants (normalized_name,display_name,subcategory_id,merchant_key,provenance,"
                "seed_version,lifecycle) VALUES (:normalized,:display,NULL,:key,:provenance,:seed_version,'active') "
                "RETURNING id"
            ),
            {
                "normalized": f"seed:{merchant.merchant_key}",
                "display": merchant.display_name,
                "key": merchant.merchant_key,
                "provenance": merchant.provenance,
                "seed_version": merchant.seed_version,
            },
        ).scalar_one()
        merchant_ids[merchant.merchant_key] = merchant_id
        for alias in merchant.aliases:
            connection.execute(
                sa.text(
                    "INSERT INTO merchant_aliases "
                    "(merchant_id,normalized_value,match_field,provider,country) "
                    "VALUES (:merchant_id,:value,:field,:provider,:country)"
                ),
                {
                    "merchant_id": merchant_id,
                    "value": alias.normalized_value,
                    "field": alias.match_field.value,
                    "provider": alias.provider,
                    "country": alias.country,
                },
            )

    connection.execute(
        sa.text("UPDATE categorization_rules SET active=false, lifecycle='deprecated' WHERE user_id IS NULL")
    )
    for rule in rules:
        connection.execute(
            sa.text(
                "INSERT INTO categorization_rules (user_id,priority,pattern_type,pattern_value,"
                "matches_subcategory_id,active,rule_key,merchant_id,match_field,match_operator,direction,provider,"
                "country,minimum_amount,maximum_amount,confidence,provenance,seed_version,lifecycle) VALUES "
                "(NULL,100,:pattern_type,:pattern_value,:target,true,:rule_key,:merchant_id,:match_field,:operator,"
                ":direction,:provider,:country,:minimum,:maximum,:confidence,:provenance,:seed_version,'active')"
            ),
            {
                "pattern_type": "merchant" if rule.merchant_key else "keyword",
                "pattern_value": rule.merchant_key or rule.pattern,
                "target": child_ids[rule.target_key],
                "rule_key": rule.rule_key,
                "merchant_id": merchant_ids.get(rule.merchant_key) if rule.merchant_key else None,
                "match_field": rule.match_field.value,
                "operator": rule.operator.value,
                "direction": rule.direction.value,
                "provider": rule.provider,
                "country": rule.country,
                "minimum": rule.minimum_amount,
                "maximum": rule.maximum_amount,
                "confidence": rule.confidence.value,
                "provenance": rule.provenance,
                "seed_version": rule.seed_version,
            },
        )

    connection.execute(sa.text("SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories))"))
    connection.execute(sa.text("SELECT setval('subcategories_id_seq', (SELECT MAX(id) FROM subcategories))"))
    migration._insert_snapshot_events(connection, definitions, public_ids, taxonomy_version, parent_ids, child_ids)


def _record_allocations(
    connection: Connection,
    run_id: str,
    public_ids: Mapping[str, str],
    parent_ids: Mapping[str, int],
    child_ids: Mapping[str, int],
) -> None:
    statement = sa.text(
        "INSERT INTO taxonomy_surrogate_allocations "
        "(node_kind,semantic_key,public_id,surrogate_id,bootstrap_run_id) "
        "VALUES (:kind,:key,:public_id,:surrogate_id,:run_id)"
    )
    for kind, allocations in (("category", parent_ids), ("subcategory", child_ids)):
        for key, surrogate_id in allocations.items():
            connection.execute(
                statement,
                {
                    "kind": kind,
                    "key": key,
                    "public_id": public_ids[key],
                    "surrogate_id": surrogate_id,
                    "run_id": run_id,
                },
            )


def _validate_postconditions(
    connection: Connection,
    public_ids: Mapping[str, str],
    parent_ids: Mapping[str, int],
    child_ids: Mapping[str, int],
) -> None:
    counts = connection.execute(
        sa.text(
            "SELECT "
            "(SELECT COUNT(*) FROM categories WHERE semantic_key IS NOT NULL AND lifecycle='active'),"
            "(SELECT COUNT(*) FROM subcategories WHERE semantic_key IS NOT NULL AND lifecycle='active'),"
            "(SELECT COUNT(*) FROM categorization_rules WHERE rule_key IS NOT NULL AND active),"
            "(SELECT COUNT(*) FROM taxonomy_surrogate_allocations),"
            "(SELECT COUNT(*) FROM outbox_events WHERE payload_json::jsonb->>'event_version'='3')"
        )
    ).one()
    if tuple(counts) != (13, 67, 82, 80, 80):
        raise RuntimeError(f"incomplete TAX-06 bootstrap state: {tuple(counts)}")
    for table, allocations in (("categories", parent_ids), ("subcategories", child_ids)):
        rows = connection.execute(
            sa.text(f"SELECT semantic_key,id,public_id FROM {table} WHERE semantic_key IS NOT NULL")
        ).all()
        actual = {key: (surrogate_id, public_id) for key, surrogate_id, public_id in rows}
        expected = {key: (surrogate_id, public_ids[key]) for key, surrogate_id in allocations.items()}
        if actual != expected:
            raise RuntimeError(f"canonical identity mismatch in {table}")


def _engine() -> Engine:
    configured_url = os.getenv("DATABASE_URL")
    if not configured_url:
        raise RuntimeError("DATABASE_URL is required")
    url = configured_url.replace("postgresql+asyncpg://", "postgresql://")
    return create_engine(url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    category_start, subcategory_start = bootstrap(_engine(), args.run_id)
    print(
        "TAX-06 bootstrap installed revision 008; "
        f"category_start={category_start} subcategory_start={subcategory_start}"
    )


if __name__ == "__main__":
    main()
