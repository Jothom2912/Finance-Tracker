"""Add CHECK constraint enforcing positive amounts.

Revision ID: 008
Revises: 007
Create Date: 2026-04-29

The application convention is unsigned amount + transaction_type enum.
Amount must always be positive (>= 0.01); direction is encoded
exclusively by the transaction_type field ('income' / 'expense').

A full-table scan on 2026-04-29 confirmed zero negative rows in both
transactions (232 rows) and planned_transactions, so this constraint
codifies an already-true invariant rather than changing behaviour.
"""

from __future__ import annotations

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_transactions_positive_amount",
        "transactions",
        "amount > 0",
    )
    op.create_check_constraint(
        "ck_planned_transactions_positive_amount",
        "planned_transactions",
        "amount > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_planned_transactions_positive_amount",
        "planned_transactions",
        type_="check",
    )
    op.drop_constraint(
        "ck_transactions_positive_amount",
        "transactions",
        type_="check",
    )
