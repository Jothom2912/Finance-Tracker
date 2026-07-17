"""Partial unique index on user rules (F1-02/F1-03).

``(user_id, pattern_type, pattern_value) WHERE user_id IS NOT NULL``:

- upsert backstop for the feedback-loop consumer (learned MERCHANT
  rules must converge on one row per user+merchant, also under
  concurrent redelivery)
- duplicate guard for user-created KEYWORD rules via the API

Seed rules (user_id IS NULL) are exempt — they are migration-managed
and may legitimately repeat pattern values across pattern types.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str = "006"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_rules_user_pattern"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "categorization_rules",
        ["user_id", "pattern_type", "pattern_value"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
        sqlite_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="categorization_rules")
