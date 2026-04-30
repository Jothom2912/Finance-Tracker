"""Seed categorization rules from SEED_MERCHANT_MAPPINGS.

Revision ID: 005
Revises: 004
Create Date: 2026-04-23

Each keyword in SEED_MERCHANT_MAPPINGS becomes one categorization_rule
row with pattern_type='keyword'.  All system rules get priority=100.
Within the same priority, the rule engine applies longest-match-first
as secondary sort — preserving the monolith's implicit ordering.

User rules (future) default to priority=50, which gives them higher
precedence than system rules.  See docs/SCHEMA.md for details.

Idempotent: skips if a rule with the same pattern_value already exists.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | None = None
depends_on: str | None = None

_SYSTEM_RULE_PRIORITY = 100


def upgrade() -> None:
    from app.domain.taxonomy import SEED_MERCHANT_MAPPINGS

    bind = op.get_bind()

    rows = bind.execute(sa.text("SELECT id, name FROM subcategories"))
    sub_lookup: dict[str, int] = {row.name: row.id for row in rows}

    for keyword, mapping in SEED_MERCHANT_MAPPINGS.items():
        sub_name = mapping["subcategory"]
        sub_id = sub_lookup.get(sub_name)

        if sub_id is None:
            continue

        existing = bind.execute(
            sa.text(
                "SELECT id FROM categorization_rules "
                "WHERE pattern_type = 'keyword' AND pattern_value = :pv AND user_id IS NULL"
            ),
            {"pv": keyword.lower()},
        ).first()

        if existing is not None:
            continue

        bind.execute(
            sa.text(
                "INSERT INTO categorization_rules "
                "(user_id, priority, pattern_type, pattern_value, matches_subcategory_id, active) "
                "VALUES (NULL, :priority, 'keyword', :pattern_value, :subcategory_id, true)"
            ),
            {
                "priority": _SYSTEM_RULE_PRIORITY,
                "pattern_value": keyword.lower(),
                "subcategory_id": sub_id,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM categorization_rules WHERE user_id IS NULL AND pattern_type = 'keyword'"))
