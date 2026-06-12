"""Initial banking-service schema.

Revision ID: 001
Revises:
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_connections",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", sa.Integer, nullable=False, index=True),
        sa.Column("user_id", sa.Integer, nullable=False, index=True),
        sa.Column("session_id", sa.String(200), nullable=False, index=True),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("bank_country", sa.String(5), nullable=False, server_default="DK"),
        sa.Column("bank_account_uid", sa.String(200), nullable=False),
        sa.Column("bank_account_iban", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'disconnected')",
            name="ck_bank_connection_status",
        ),
    )

    op.create_table(
        "pending_authorizations",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(100), unique=True, nullable=False),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("consumed_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "accounts_projection",
        sa.Column("account_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("user_id", sa.Integer, nullable=False, index=True),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_outbox_pending_poll",
        "outbox_events",
        ["status", "next_attempt_at", "created_at"],
    )

    op.create_table(
        "processed_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("correlation_id", sa.String(255), nullable=False),
        sa.Column("consumer_name", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("correlation_id", "consumer_name", name="uq_processed_event"),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("outbox_events")
    op.drop_table("accounts_projection")
    op.drop_table("pending_authorizations")
    op.drop_table("bank_connections")
