"""Activate the additive UUIDv7 taxonomy and constrained global seeds.

Revision ID: 008
Revises: 007
Create Date: 2026-08-01

Legacy taxonomy rows and their references remain intact for TAX-07.  New target rows
use separate integer surrogates plus canonical UUIDv7/key identity.  Full-state v3
events are inserted into the transactional outbox in the same transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from contracts.events.category import CategoryCreatedEvent, SubCategoryCreatedEvent

revision: str = "008"
down_revision: str = "007"
branch_labels = None
depends_on = None

_TIMESTAMP = datetime(2026, 8, 1, tzinfo=timezone.utc)
_NAMESPACE = uuid.UUID("fdab684d-08d5-4b65-b43f-e8ff67aaf943")


def _load_snapshot():
    from app.domain.merchant_aliases import MERCHANTS
    from app.domain.seed_rules import GLOBAL_RULES
    from app.domain.taxonomy_definitions import TAXONOMY_DEFINITIONS
    from app.domain.taxonomy_identity import TAXONOMY_PUBLIC_IDS, TAXONOMY_VERSION

    return TAXONOMY_DEFINITIONS, TAXONOMY_PUBLIC_IDS, TAXONOMY_VERSION, MERCHANTS, GLOBAL_RULES


def upgrade() -> None:
    _add_schema()
    bind = op.get_bind()
    definitions, public_ids, taxonomy_version, merchants, rules = _load_snapshot()

    bind.execute(
        sa.text("UPDATE categories SET lifecycle='deprecated', deprecated_in_version=1 WHERE semantic_key IS NULL")
    )
    bind.execute(
        sa.text("UPDATE subcategories SET lifecycle='deprecated', deprecated_in_version=1 WHERE semantic_key IS NULL")
    )

    parent_ids: dict[str, int] = {}
    child_ids: dict[str, int] = {}
    next_category_id = 11
    next_subcategory_id = 42
    for definition in definitions:
        if definition.parent_key is None:
            entity_id = next_category_id
            next_category_id += 1
            parent_ids[definition.semantic_key] = entity_id
            bind.execute(
                sa.text(
                    "INSERT INTO categories (id,name,type,display_order,public_id,semantic_key,description,"
                    "taxonomy_version,lifecycle) VALUES (:id,:name,:type,:display_order,:public_id,:key,:description,1,'active')"
                ),
                {
                    "id": entity_id,
                    "name": definition.display_name,
                    "type": definition.category_type.value,
                    "display_order": len(parent_ids),
                    "public_id": public_ids[definition.semantic_key],
                    "key": definition.semantic_key,
                    "description": definition.description,
                },
            )

    child_order: dict[str, int] = {}
    for definition in definitions:
        if definition.parent_key is None:
            continue
        entity_id = next_subcategory_id
        next_subcategory_id += 1
        child_ids[definition.semantic_key] = entity_id
        child_order[definition.parent_key] = child_order.get(definition.parent_key, 0) + 1
        bind.execute(
            sa.text(
                "INSERT INTO subcategories (id,name,category_id,is_default,public_id,semantic_key,description,"
                "is_fallback,taxonomy_version,lifecycle) VALUES "
                "(:id,:name,:category_id,true,:public_id,:key,:description,:is_fallback,1,'active')"
            ),
            {
                "id": entity_id,
                "name": definition.display_name,
                "category_id": parent_ids[definition.parent_key],
                "public_id": public_ids[definition.semantic_key],
                "key": definition.semantic_key,
                "description": definition.description,
                "is_fallback": definition.is_fallback,
            },
        )

    merchant_ids: dict[str, int] = {}
    for merchant in merchants:
        merchant_id = bind.execute(
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
            bind.execute(
                sa.text(
                    "INSERT INTO merchant_aliases (merchant_id,normalized_value,match_field,provider,country) "
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

    bind.execute(sa.text("UPDATE categorization_rules SET active=false, lifecycle='deprecated' WHERE user_id IS NULL"))
    for rule in rules:
        bind.execute(
            sa.text(
                "INSERT INTO categorization_rules (user_id,priority,pattern_type,pattern_value,matches_subcategory_id,"
                "active,rule_key,merchant_id,match_field,match_operator,direction,provider,country,minimum_amount,"
                "maximum_amount,confidence,provenance,seed_version,lifecycle) VALUES "
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

    bind.execute(sa.text("SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories))"))
    bind.execute(sa.text("SELECT setval('subcategories_id_seq', (SELECT MAX(id) FROM subcategories))"))
    _insert_snapshot_events(bind, definitions, public_ids, taxonomy_version, parent_ids, child_ids)


def _add_schema() -> None:
    for table in ("categories", "subcategories"):
        op.add_column(table, sa.Column("public_id", sa.String(36), nullable=True))
        op.add_column(table, sa.Column("semantic_key", sa.String(100), nullable=True))
        op.add_column(table, sa.Column("description", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("taxonomy_version", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("lifecycle", sa.String(20), nullable=False, server_default="active"))
        op.add_column(table, sa.Column("deprecated_in_version", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("replaced_by_public_id", sa.String(36), nullable=True))
        op.create_index(f"uq_{table}_public_id", table, ["public_id"], unique=True)
        op.create_index(f"uq_{table}_semantic_key", table, ["semantic_key"], unique=True)
        op.create_check_constraint(
            f"ck_{table}_canonical_identity",
            table,
            "(semantic_key IS NULL AND public_id IS NULL AND taxonomy_version IS NULL) OR "
            "(semantic_key IS NOT NULL AND public_id IS NOT NULL AND taxonomy_version IS NOT NULL)",
        )
    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.create_index(
        "uq_categories_active_name",
        "categories",
        ["name"],
        unique=True,
        postgresql_where=sa.text("lifecycle = 'active'"),
    )
    op.add_column("subcategories", sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index(
        "uq_subcategories_active_fallback",
        "subcategories",
        ["category_id"],
        unique=True,
        postgresql_where=sa.text("lifecycle = 'active' AND is_fallback"),
    )

    op.alter_column("merchants", "subcategory_id", existing_type=sa.Integer(), nullable=True)
    for name, type_ in (
        ("merchant_key", sa.String(100)),
        ("provenance", sa.Text()),
        ("seed_version", sa.String(50)),
        ("lifecycle", sa.String(20)),
    ):
        op.add_column(
            "merchants",
            sa.Column(
                name,
                type_,
                nullable=True if name != "lifecycle" else False,
                server_default="active" if name == "lifecycle" else None,
            ),
        )
    op.create_index("uq_merchants_merchant_key", "merchants", ["merchant_key"], unique=True)
    op.create_table(
        "merchant_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("normalized_value", sa.String(200), nullable=False),
        sa.Column("match_field", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("normalized_value", "match_field", "provider", "country", name="uq_merchant_alias_scope"),
    )
    op.create_index("ix_merchant_aliases_merchant_id", "merchant_aliases", ["merchant_id"])

    rule_columns = (
        sa.Column("rule_key", sa.String(150), nullable=True),
        sa.Column("merchant_id", sa.Integer(), nullable=True),
        sa.Column("match_field", sa.String(30), nullable=True),
        sa.Column("match_operator", sa.String(30), nullable=True),
        sa.Column("direction", sa.String(20), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("minimum_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("maximum_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),
        sa.Column("provenance", sa.Text(), nullable=True),
        sa.Column("seed_version", sa.String(50), nullable=True),
        sa.Column("lifecycle", sa.String(20), nullable=False, server_default="active"),
    )
    for column in rule_columns:
        op.add_column("categorization_rules", column)
    op.create_index("uq_rules_rule_key", "categorization_rules", ["rule_key"], unique=True)
    op.create_foreign_key("fk_rules_merchant", "categorization_rules", "merchants", ["merchant_id"], ["id"])
    op.create_check_constraint(
        "ck_rules_amount_bounds",
        "categorization_rules",
        "minimum_amount IS NULL OR maximum_amount IS NULL OR minimum_amount <= maximum_amount",
    )
    op.create_check_constraint(
        "ck_rules_target_seed_complete",
        "categorization_rules",
        "rule_key IS NULL OR (match_field IS NOT NULL AND match_operator IS NOT NULL "
        "AND direction IS NOT NULL AND confidence IS NOT NULL AND provenance IS NOT NULL "
        "AND seed_version IS NOT NULL AND ((merchant_id IS NOT NULL AND pattern_type = 'merchant') "
        "OR (merchant_id IS NULL AND pattern_type <> 'merchant')))",
    )


def _insert_snapshot_events(bind, definitions, public_ids, taxonomy_version, parent_ids, child_ids) -> None:
    rows = []
    for definition in definitions:
        key = definition.semantic_key
        correlation_id = str(uuid.uuid5(_NAMESPACE, f"taxonomy-v1:{key}:correlation"))
        common = dict(
            event_version=3,
            public_id=public_ids[key],
            semantic_key=key,
            taxonomy_version=taxonomy_version,
            lifecycle="active",
            description=definition.description,
            correlation_id=correlation_id,
            timestamp=_TIMESTAMP,
        )
        if definition.parent_key is None:
            event = CategoryCreatedEvent(
                category_id=parent_ids[key],
                name=definition.display_name,
                category_type=definition.category_type.value,
                display_order=list(parent_ids).index(key) + 1,
                **common,
            )
            aggregate_type, aggregate_id = "category", parent_ids[key]
        else:
            event = SubCategoryCreatedEvent(
                subcategory_id=child_ids[key],
                name=definition.display_name,
                category_id=parent_ids[definition.parent_key],
                parent_public_id=public_ids[definition.parent_key],
                is_default=True,
                is_fallback=definition.is_fallback,
                **common,
            )
            aggregate_type, aggregate_id = "subcategory", child_ids[key]
        rows.append(
            {
                "id": str(uuid.uuid5(_NAMESPACE, f"taxonomy-v1:{key}:outbox")),
                "aggregate_type": aggregate_type,
                "aggregate_id": str(aggregate_id),
                "event_type": event.event_type,
                "payload_json": event.to_json(),
                "correlation_id": correlation_id,
            }
        )
    statement = sa.text(
        "INSERT INTO outbox_events (id,aggregate_type,aggregate_id,event_type,payload_json,correlation_id,status,attempts) "
        "VALUES (:id,:aggregate_type,:aggregate_id,:event_type,:payload_json,:correlation_id,'pending',0) "
        "ON CONFLICT (id) DO NOTHING"
    )
    for row in rows:
        bind.execute(statement, row)


def downgrade() -> None:
    bind = op.get_bind()
    referenced = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM categorization_results r JOIN subcategories s ON s.id=r.subcategory_id "
            "WHERE s.semantic_key IS NOT NULL"
        )
    ).scalar_one()
    if referenced:
        raise RuntimeError("TAX-06 target taxonomy is referenced; use forward repair instead of downgrade")
    bind.execute(sa.text("DELETE FROM outbox_events WHERE payload_json::jsonb ->> 'event_version' = '3'"))
    bind.execute(sa.text("DELETE FROM categorization_rules WHERE rule_key IS NOT NULL"))
    bind.execute(sa.text("DELETE FROM merchant_aliases"))
    bind.execute(sa.text("DELETE FROM merchants WHERE merchant_key IS NOT NULL"))
    bind.execute(sa.text("DELETE FROM subcategories WHERE semantic_key IS NOT NULL"))
    bind.execute(sa.text("DELETE FROM categories WHERE semantic_key IS NOT NULL"))
    bind.execute(
        sa.text("UPDATE categories SET lifecycle='active', deprecated_in_version=NULL WHERE semantic_key IS NULL")
    )
    bind.execute(
        sa.text("UPDATE subcategories SET lifecycle='active', deprecated_in_version=NULL WHERE semantic_key IS NULL")
    )
    bind.execute(sa.text("UPDATE categorization_rules SET active=true, lifecycle='active' WHERE user_id IS NULL"))
    op.drop_constraint("ck_rules_amount_bounds", "categorization_rules", type_="check")
    op.drop_constraint("ck_rules_target_seed_complete", "categorization_rules", type_="check")
    op.drop_constraint("fk_rules_merchant", "categorization_rules", type_="foreignkey")
    op.drop_index("uq_rules_rule_key", table_name="categorization_rules")
    for name in (
        "lifecycle",
        "seed_version",
        "provenance",
        "confidence",
        "maximum_amount",
        "minimum_amount",
        "country",
        "provider",
        "direction",
        "match_operator",
        "match_field",
        "merchant_id",
        "rule_key",
    ):
        op.drop_column("categorization_rules", name)
    op.drop_table("merchant_aliases")
    op.drop_index("uq_merchants_merchant_key", table_name="merchants")
    for name in ("lifecycle", "seed_version", "provenance", "merchant_key"):
        op.drop_column("merchants", name)
    op.alter_column("merchants", "subcategory_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("uq_subcategories_active_fallback", table_name="subcategories")
    op.drop_column("subcategories", "is_fallback")
    op.drop_index("uq_categories_active_name", table_name="categories")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])
    for table in ("subcategories", "categories"):
        op.drop_constraint(f"ck_{table}_canonical_identity", table, type_="check")
        op.drop_index(f"uq_{table}_semantic_key", table_name=table)
        op.drop_index(f"uq_{table}_public_id", table_name=table)
        for name in (
            "replaced_by_public_id",
            "deprecated_in_version",
            "lifecycle",
            "taxonomy_version",
            "description",
            "semantic_key",
            "public_id",
        ):
            op.drop_column(table, name)
