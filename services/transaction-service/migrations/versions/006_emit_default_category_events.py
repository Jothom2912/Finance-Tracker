"""Tombstone — category seed events moved to categorization-service.

Revision ID: 006
Revises: 005
Create Date: 2026-04-17 (tombstoned 2026-07-05)

This migration used to emit ``category.created`` v1 events for the ten
seed categories via the outbox. Per ADR-003 the taxonomy is owned by
categorization-service, which re-announces the full seed taxonomy
(categories v2 + subcategories) in its own migration 006 — emitting
category events from this service would be publishing from the wrong
owner.

The revision id must survive as a no-op tombstone: existing databases
have "006" in their ``alembic_version`` history, so deleting the file
would break ``alembic upgrade``. Databases that already ran the
original version keep their (long since published) outbox rows —
events are never retracted.
"""

from __future__ import annotations

revision: str = "006"
down_revision: str = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
