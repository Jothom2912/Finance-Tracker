"""Record and enforce TAX-06 surrogate allocations.

Revision ID: 009
Revises: 008
Create Date: 2026-08-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS taxonomy_surrogate_allocations ("
            "node_kind VARCHAR(20) NOT NULL, semantic_key VARCHAR(100) NOT NULL, "
            "public_id VARCHAR(36) NOT NULL, surrogate_id INTEGER NOT NULL, "
            "bootstrap_run_id VARCHAR(100) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
            "CONSTRAINT pk_taxonomy_surrogate_allocations PRIMARY KEY (node_kind, semantic_key), "
            "CONSTRAINT uq_taxonomy_allocation_public_id UNIQUE (public_id), "
            "CONSTRAINT uq_taxonomy_allocation_surrogate UNIQUE (node_kind, surrogate_id))"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO taxonomy_surrogate_allocations "
            "(node_kind,semantic_key,public_id,surrogate_id,bootstrap_run_id) "
            "SELECT 'category',semantic_key,public_id,id,'alembic-008' FROM categories "
            "WHERE semantic_key IS NOT NULL ON CONFLICT (node_kind,semantic_key) DO NOTHING"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO taxonomy_surrogate_allocations "
            "(node_kind,semantic_key,public_id,surrogate_id,bootstrap_run_id) "
            "SELECT 'subcategory',semantic_key,public_id,id,'alembic-008' FROM subcategories "
            "WHERE semantic_key IS NOT NULL ON CONFLICT (node_kind,semantic_key) DO NOTHING"
        )
    )
    counts = bind.execute(
        sa.text(
            "SELECT "
            "(SELECT COUNT(*) FROM taxonomy_surrogate_allocations WHERE node_kind='category'),"
            "(SELECT COUNT(*) FROM taxonomy_surrogate_allocations WHERE node_kind='subcategory'),"
            "(SELECT COUNT(*) FROM categories c JOIN taxonomy_surrogate_allocations a "
            "ON a.node_kind='category' AND a.semantic_key=c.semantic_key "
            "AND a.public_id=c.public_id AND a.surrogate_id=c.id),"
            "(SELECT COUNT(*) FROM subcategories s JOIN taxonomy_surrogate_allocations a "
            "ON a.node_kind='subcategory' AND a.semantic_key=s.semantic_key "
            "AND a.public_id=s.public_id AND a.surrogate_id=s.id)"
        )
    ).one()
    if tuple(counts) != (13, 67, 13, 67):
        raise RuntimeError(f"TAX-06 surrogate allocation mismatch: {tuple(counts)}")
    bind.execute(sa.text("SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories))"))
    bind.execute(sa.text("SELECT setval('subcategories_id_seq', (SELECT MAX(id) FROM subcategories))"))


def downgrade() -> None:
    bind = op.get_bind()
    referenced = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM categorization_results r "
            "JOIN subcategories s ON s.id=r.subcategory_id WHERE s.semantic_key IS NOT NULL"
        )
    ).scalar_one()
    if referenced:
        raise RuntimeError("TAX-06 target taxonomy is referenced; keep allocation ledger")
    op.drop_table("taxonomy_surrogate_allocations")
