"""Create all categorization-service tables.

Revision ID: 001
Revises:
Create Date: 2026-04-23

Seven tables: categories, subcategories, merchants, categorization_rules,
categorization_results, outbox_events, processed_events.

No seed data — that follows in migrations 002-005.
See docs/SCHEMA.md for design rationale.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(45), nullable=False, unique=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_categories_name", "categories", ["name"])

    op.create_table(
        "subcategories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subcategories_category_id", "subcategories", ["category_id"])
    op.create_index("ix_subcategories_name", "subcategories", ["name"])

    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("normalized_name", sa.String(200), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column(
            "subcategory_id",
            sa.Integer,
            sa.ForeignKey("subcategories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("transaction_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_user_confirmed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_merchants_normalized_name", "merchants", ["normalized_name"], unique=True)
    op.create_index("ix_merchants_subcategory_id", "merchants", ["subcategory_id"])

    op.create_table(
        "categorization_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("pattern_type", sa.String(30), nullable=False),
        sa.Column("pattern_value", sa.Text, nullable=False),
        sa.Column(
            "matches_subcategory_id",
            sa.Integer,
            sa.ForeignKey("subcategories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rules_active_priority", "categorization_rules", ["active", "priority"])
    op.execute("CREATE INDEX ix_rules_user ON categorization_rules (user_id) WHERE user_id IS NOT NULL")

    op.create_table(
        "categorization_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("transaction_id", sa.Integer, nullable=False),
        sa.Column("category_id", sa.Integer, nullable=False),
        sa.Column("subcategory_id", sa.Integer, nullable=False),
        sa.Column("merchant_id", sa.Integer, nullable=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_results_transaction_latest",
        "categorization_results",
        ["transaction_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_outbox_pending_poll",
        "outbox_events",
        ["status", "next_attempt_at", "created_at"],
    )

    op.create_table(
        "processed_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("consumer_name", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_processed_events",
        "processed_events",
        ["message_id", "consumer_name"],
        unique=True,
    )
    op.create_index("ix_processed_at", "processed_events", ["processed_at"])


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("outbox_events")
    op.drop_table("categorization_results")
    op.drop_table("categorization_rules")
    op.drop_table("merchants")
    op.drop_table("subcategories")
    op.drop_table("categories")
