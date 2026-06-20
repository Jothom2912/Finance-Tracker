"""Backfill: split a transaction's category name into parent + subcategory.

Before the category-consistency work (Fase 2), the categorized-event consumer
wrote the SUBCATEGORY name into ``category_name``.  ``category_name`` must
always hold the PARENT name, with the sub-level name in ``subcategory_name``.

This backfill repairs rows mis-populated that way:

- A row is "dirty" when ``category_name`` does not equal the parent name for
  its ``category_id`` (i.e. it currently holds the subcategory name).
- For such rows: move the current ``category_name`` into ``subcategory_name``
  and set ``category_name`` to the parent name from the local ``categories``
  table.
- Manually-created rows (where ``category_name`` already equals the parent
  name) are left untouched.

Idempotent by construction: after a run, ``category_name`` equals the parent
name and ``subcategory_name`` is set, so the WHERE clause matches nothing on a
re-run.  The ``subcategory_name IS NULL`` guard prevents clobbering a value
already written by the new consumer.

This module deliberately imports nothing from ``app.config`` so it is safe to
import from an Alembic migration without requiring runtime settings.

Standalone use::

    python -m app.maintenance.backfill_subcategory_name
"""

from __future__ import annotations

BACKFILL_SQL = """
UPDATE transactions AS t
SET subcategory_name = t.category_name,
    category_name = c.name
FROM categories AS c
WHERE t.category_id = c.id
  AND t.category_name IS NOT NULL
  AND t.category_name <> c.name
  AND t.subcategory_name IS NULL
"""


def main() -> None:  # pragma: no cover - thin operational entrypoint
    """Run the backfill against ``DATABASE_URL`` (sync driver)."""
    import os

    from sqlalchemy import create_engine, text

    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(url)
    with engine.begin() as conn:
        result = conn.execute(text(BACKFILL_SQL))
        print(f"Backfill complete: {result.rowcount} row(s) corrected")


if __name__ == "__main__":  # pragma: no cover
    main()
