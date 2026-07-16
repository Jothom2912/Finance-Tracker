"""Integration tests for Alembic migrations 005 + 006.

These tests run ``alembic upgrade head`` against a real Postgres 16
container (via Testcontainers) and assert the resulting state matches
the seed contract the rest of the system depends on.

What this suite catches that the unit tests can't:

* **Postgres-specific SQL.**  Migrations use ``ON CONFLICT``,
  ``setval`` and parameterised ``ANY(:ids)`` — none of which behave
  identically on SQLite (the rest of the test suite's fixture DB).
* **Alembic ordering + metadata.**  That the migration chain climbs
  correctly from base → head without revision conflicts.
* **Round-trip idempotency.**  That ``downgrade base`` + ``upgrade
  head`` lands in the same state, not a drifted one.
* **Referential integrity under the current schema design.**
  ``transactions.category_id`` has no FK on purpose (cross-service
  convention), but every row produced by the seed-driven rule engine
  must still reference an extant category after upgrade.  This is
  item (2) of the drift audit folded into the same Postgres fixture.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine


def _upgrade_head(alembic_cfg) -> None:  # type: ignore[no-untyped-def]
    from alembic import command

    command.upgrade(alembic_cfg, "head")


def _downgrade_to(alembic_cfg, revision: str) -> None:  # type: ignore[no-untyped-def]
    from alembic import command

    command.downgrade(alembic_cfg, revision)


# ─────────────────────────────────────────────────────────────
# Migration 005 — default category seed
# ─────────────────────────────────────────────────────────────


class TestMigration005SeedsCategories:
    def test_upgrade_produces_ten_pinned_categories(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            rows = conn.execute(sa.text("SELECT id, name, type FROM categories ORDER BY id")).fetchall()

        assert len(rows) == 10
        assert [r.id for r in rows] == list(range(1, 11))
        assert ("Mad & drikke", "expense") == (rows[0].name, rows[0].type)
        assert ("Overfoersler", "transfer") == (rows[9].name, rows[9].type)

    def test_sequence_bumped_past_seeded_ids(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """After the pinned insert, user-created categories via the API
        must start at id=11 — not collide with id=1..10.
        """
        _upgrade_head(alembic_cfg)

        with clean_db.begin() as conn:
            next_id = conn.execute(
                sa.text("INSERT INTO categories (name, type) VALUES ('Test', 'expense') RETURNING id")
            ).scalar()

        assert next_id == 11


# ─────────────────────────────────────────────────────────────
# Migration 010 — subcategories read model (ADR-003)
# ─────────────────────────────────────────────────────────────


class TestMigration010SubcategoriesReadModel:
    def test_upgrade_creates_and_seeds_41_subcategories(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            rows = conn.execute(sa.text("SELECT id, name, category_id FROM subcategories ORDER BY id")).fetchall()

        assert len(rows) == 41
        assert (rows[0].id, rows[0].name, rows[0].category_id) == (1, "Dagligvarer", 1)
        # The rule engine's fallback subcategory must be present.
        anden = next(r for r in rows if r.name == "Anden")
        assert (anden.id, anden.category_id) == (32, 8)


# ─────────────────────────────────────────────────────────────
# Migration 011 — composite index on the import dedup key (H15)
# ─────────────────────────────────────────────────────────────


class TestMigration011DedupIndex:
    def test_upgrade_creates_composite_dedup_index(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """The batch anti-join in ``find_existing_dedup_keys`` relies on
        this index — column order must match the dedup key convention
        ``(user_id, account_id, date, amount, description)``."""
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            indexdef = conn.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'transactions' "
                    "AND indexname = 'ix_transactions_dedup_key'"
                )
            ).scalar()

        assert indexdef is not None
        assert "(user_id, account_id, date, amount, description)" in indexdef

    def test_dedup_index_is_not_unique(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Deliberately non-unique: identical keys are legitimate outside
        the import paths (e.g. two identical manual purchases the same
        day) — see the migration 011 docstring.  Guard against a future
        "tightening" that would break those writes."""
        _upgrade_head(alembic_cfg)

        with clean_db.begin() as conn:
            for _ in range(2):
                conn.execute(
                    sa.text(
                        "INSERT INTO transactions "
                        "(user_id, account_id, account_name, amount, transaction_type, date, description) "
                        "VALUES (1, 1, 'Test', :amt, 'expense', '2026-01-01', 'Kaffe')"
                    ),
                    {"amt": Decimal("35.00")},
                )

        with clean_db.connect() as conn:
            count = conn.execute(sa.text("SELECT COUNT(*) FROM transactions WHERE description = 'Kaffe'")).scalar()
        assert count == 2

    def test_downgrade_drops_the_index(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        _upgrade_head(alembic_cfg)
        _downgrade_to(alembic_cfg, "010")

        with clean_db.connect() as conn:
            indexdef = conn.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'transactions' "
                    "AND indexname = 'ix_transactions_dedup_key'"
                )
            ).scalar()

        assert indexdef is None


# ─────────────────────────────────────────────────────────────
# Migration 012 — external_id + currency (P2-09, H10)
# ─────────────────────────────────────────────────────────────


class TestMigration012ExternalIdCurrency:
    def test_columns_added_and_currency_backfilled(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """A row that exists before 012 runs must come out with
        currency='DKK' (server_default backfill) and external_id NULL."""
        from alembic import command

        command.upgrade(alembic_cfg, "011")

        with clean_db.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO transactions "
                    "(user_id, account_id, account_name, amount, transaction_type, date, description) "
                    "VALUES (1, 1, 'Test', :amt, 'expense', '2026-01-01', 'Pre-012')"
                ),
                {"amt": Decimal("10.00")},
            )

        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            row = conn.execute(
                sa.text("SELECT external_id, currency FROM transactions WHERE description = 'Pre-012'")
            ).one()
        assert row.external_id is None
        assert row.currency == "DKK"

    def test_partial_unique_index_definition(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            indexdef = conn.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'transactions' "
                    "AND indexname = 'uq_transactions_account_external_id'"
                )
            ).scalar()

        assert indexdef is not None
        assert "UNIQUE" in indexdef
        assert "(account_id, external_id)" in indexdef
        assert "WHERE (external_id IS NOT NULL)" in indexdef

    def test_duplicate_external_id_rejected_null_duplicates_allowed(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """The unique index is the concurrent-import backstop — but ONLY
        for id-bearing rows: NULL external_ids (manual/CSV) must stay
        freely duplicable, or migration 011's guarantee breaks."""
        from sqlalchemy.exc import IntegrityError

        _upgrade_head(alembic_cfg)

        insert = sa.text(
            "INSERT INTO transactions "
            "(user_id, account_id, account_name, amount, transaction_type, date, description, external_id) "
            "VALUES (1, 1, 'Test', :amt, 'expense', '2026-01-01', 'Bank', :ext)"
        )

        with clean_db.begin() as conn:
            conn.execute(insert, {"amt": Decimal("10.00"), "ext": "EB-1"})

        with pytest.raises(IntegrityError):
            with clean_db.begin() as conn:
                conn.execute(insert, {"amt": Decimal("10.00"), "ext": "EB-1"})

        # Same external_id on ANOTHER account is fine …
        with clean_db.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO transactions "
                    "(user_id, account_id, account_name, amount, transaction_type, date, external_id) "
                    "VALUES (1, 2, 'Other', :amt, 'expense', '2026-01-01', 'EB-1')"
                ),
                {"amt": Decimal("10.00")},
            )
            # … and NULL external_id duplicates stay legal.
            for _ in range(2):
                conn.execute(insert, {"amt": Decimal("10.00"), "ext": None})

        with clean_db.connect() as conn:
            count = conn.execute(sa.text("SELECT COUNT(*) FROM transactions")).scalar()
        assert count == 4

    def test_downgrade_drops_index_and_columns(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        _upgrade_head(alembic_cfg)
        _downgrade_to(alembic_cfg, "011")

        with clean_db.connect() as conn:
            indexdef = conn.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'transactions' "
                    "AND indexname = 'uq_transactions_account_external_id'"
                )
            ).scalar()
            columns = {
                r.column_name
                for r in conn.execute(
                    sa.text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name = 'transactions'"
                    )
                )
            }

        assert indexdef is None
        assert "external_id" not in columns
        assert "currency" not in columns


# ─────────────────────────────────────────────────────────────
# Migration 006 — tombstoned (taxonomy events moved to cat-service)
# ─────────────────────────────────────────────────────────────


class TestMigration006IsTombstoned:
    def test_no_category_outbox_rows_on_fresh_upgrade(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Per ADR-003 category events are emitted by categorization-
        service; a fresh transaction-service DB must not publish
        category.created from the wrong owner."""
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            outbox_count = conn.execute(
                sa.text("SELECT COUNT(*) FROM outbox_events WHERE aggregate_type='category'")
            ).scalar()

        assert outbox_count == 0


# ─────────────────────────────────────────────────────────────
# Round-trip + idempotency
# ─────────────────────────────────────────────────────────────


class TestMigrationRoundTrip:
    def test_upgrade_is_idempotent_on_second_run(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Running upgrade head twice must not duplicate anything.
        The ``ON CONFLICT (id) DO NOTHING`` clauses in 005 and 010 are
        what guarantee this — test exists to catch a future migration
        that forgets them.
        """
        _upgrade_head(alembic_cfg)
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            cat_count = conn.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar()
            sub_count = conn.execute(sa.text("SELECT COUNT(*) FROM subcategories")).scalar()

        assert cat_count == 10
        assert sub_count == 41

    def test_downgrade_then_upgrade_returns_to_same_state(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Full round-trip: upgrade to head, downgrade to 004 (below
        the seed migrations), upgrade back — seeds must be restored.
        """
        _upgrade_head(alembic_cfg)
        _downgrade_to(alembic_cfg, "004")

        with clean_db.connect() as conn:
            after_downgrade_cats = conn.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar()
        assert after_downgrade_cats == 0

        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            cat_count = conn.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar()
            sub_count = conn.execute(sa.text("SELECT COUNT(*) FROM subcategories")).scalar()
        assert cat_count == 10
        assert sub_count == 41


# ─────────────────────────────────────────────────────────────
# Item (2) — orphan category_id invariant
# ─────────────────────────────────────────────────────────────


class TestNoOrphanCategoryIds:
    def test_fresh_upgrade_has_zero_orphan_transactions(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Baseline: no transactions exist yet after a fresh upgrade,
        so orphan count is trivially zero.  The real value of this
        test is as a harness — if a future migration accidentally
        inserts transactions referencing non-existent categories, the
        same query catches it.
        """
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            orphans = conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM transactions t "
                    "LEFT JOIN categories c ON c.id = t.category_id "
                    "WHERE t.category_id IS NOT NULL AND c.id IS NULL"
                )
            ).scalar()

        assert orphans == 0

    def test_orphan_detection_query_actually_works(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Insert a deliberately-orphaned transaction and verify the
        query catches it.  Without this test, the zero-orphan assertion
        above could silently drift if the query was wrong.
        """
        _upgrade_head(alembic_cfg)

        with clean_db.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO transactions "
                    "(user_id, account_id, account_name, category_id, amount, "
                    " transaction_type, date) "
                    "VALUES (1, 1, 'Test', 9999, :amt, 'expense', '2026-01-01')"
                ),
                {"amt": Decimal("100.00")},
            )

        with clean_db.connect() as conn:
            orphans = conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM transactions t "
                    "LEFT JOIN categories c ON c.id = t.category_id "
                    "WHERE t.category_id IS NOT NULL AND c.id IS NULL"
                )
            ).scalar()

        assert orphans == 1
