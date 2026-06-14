"""create saga_instances and saga_step_log tables

Revision ID: 001
Revises:
Create Date: 2026-06-14 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saga_instances",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("saga_type", sa.String(100), nullable=False),
        sa.Column("correlation_id", sa.String(200), nullable=False, unique=True),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="started"),
        sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_saga_instances_active",
        "saga_instances",
        ["status"],
        postgresql_where=sa.text("status IN ('started', 'compensating')"),
    )

    op.create_table(
        "saga_step_log",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("saga_id", sa.Uuid(as_uuid=False), sa.ForeignKey("saga_instances.id"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("command_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reply_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compensated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.UniqueConstraint("saga_id", "step_index", name="uq_saga_step_log_saga_step"),
    )


def downgrade() -> None:
    op.drop_table("saga_step_log")
    op.drop_index("ix_saga_instances_active", table_name="saga_instances")
    op.drop_table("saga_instances")
