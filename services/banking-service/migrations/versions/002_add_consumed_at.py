"""No-op placeholder — consumed_at already exists in 001.

Revision ID: 002
Revises: 001
Create Date: 2026-06-12

Existing dev databases may already be stamped at 002. Keep this revision
so Alembic can resolve the chain; fresh installs run this after 001 with
no schema change.
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
