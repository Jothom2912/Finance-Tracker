"""Add updated_at to users.

Revision ID: 003
Revises: 002
Create Date: 2026-07-29

F2-08: users bliver mutérbar for første gang (password- og
brugernavn-skift). Uden dette felt er "hvornår blev denne bruger
ændret" ubesvarligt — repoets konvention er audit-trail frem for
tavse mutationer.

Nullable med vilje: eksisterende rækker er aldrig blevet ændret, og
NULL siger netop det. Et backfill til created_at ville lyve om en
opdatering der ikke fandt sted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "updated_at")
