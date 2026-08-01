"""constrain persisted goal status

Revision ID: 006
Revises: 005
Create Date: 2026-08-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # completed/expired are derived response states, not persisted lifecycle
    # inputs. Unknown and legacy NULL values already behaved as active in the
    # domain fallback, so make that repair explicit before enforcing the rule.
    op.execute(sa.text("UPDATE goals SET status = 'active' WHERE status IS NULL OR status NOT IN ('active', 'paused')"))
    with op.batch_alter_table("goals") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.String(length=45),
            nullable=False,
            server_default="active",
        )
        batch.create_check_constraint(
            "ck_goals_status_stored",
            "status IN ('active', 'paused')",
        )


def downgrade() -> None:
    with op.batch_alter_table("goals") as batch:
        batch.drop_constraint("ck_goals_status_stored", type_="check")
        batch.alter_column(
            "status",
            existing_type=sa.String(length=45),
            nullable=True,
            server_default=None,
        )
