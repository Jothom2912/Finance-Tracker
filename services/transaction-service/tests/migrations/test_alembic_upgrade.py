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

import json
from decimal import Decimal

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
            rows = conn.execute(
                sa.text("SELECT id, name, type FROM categories ORDER BY id")
            ).fetchall()

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
# Migration 006 — outbox events for default categories
# ─────────────────────────────────────────────────────────────


class TestMigration006EmitsOutboxEvents:
    def test_upgrade_produces_ten_pending_outbox_rows(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT aggregate_id, event_type, status, payload_json "
                    "FROM outbox_events "
                    "WHERE aggregate_type='category' "
                    "ORDER BY aggregate_id::int"
                )
            ).fetchall()

        assert len(rows) == 10
        assert all(r.status == "pending" for r in rows)
        assert all(r.event_type == "category.created" for r in rows)
        assert [int(r.aggregate_id) for r in rows] == list(range(1, 11))

    def test_event_payloads_roundtrip_through_pydantic(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Every outbox row must deserialise back into
        ``CategoryCreatedEvent`` — otherwise the consumer would reject
        the event at runtime.
        """
        from contracts.events.category import CategoryCreatedEvent

        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT aggregate_id, payload_json FROM outbox_events "
                    "WHERE aggregate_type='category'"
                )
            ).fetchall()

        for row in rows:
            event = CategoryCreatedEvent.model_validate_json(row.payload_json)
            assert event.category_id == int(row.aggregate_id)

    def test_payload_names_match_seeded_categories(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """The event's ``name`` must match the seeded row's ``name``
        for the projection to land consistently on the monolith side.
        """
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            categories = {r.id: r.name for r in conn.execute(sa.text("SELECT id, name FROM categories")).fetchall()}
            outbox = conn.execute(
                sa.text("SELECT aggregate_id, payload_json FROM outbox_events WHERE aggregate_type='category'")
            ).fetchall()

        for row in outbox:
            payload = json.loads(row.payload_json)
            assert payload["name"] == categories[int(row.aggregate_id)]


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
        The ``ON CONFLICT (id) DO NOTHING`` clauses in 005 and 006 are
        what guarantee this — test exists to catch a future migration
        that forgets them.
        """
        _upgrade_head(alembic_cfg)
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            cat_count = conn.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar()
            outbox_count = conn.execute(
                sa.text("SELECT COUNT(*) FROM outbox_events WHERE aggregate_type='category'")
            ).scalar()

        assert cat_count == 10
        assert outbox_count == 10

    def test_downgrade_then_upgrade_returns_to_same_state(
        self,
        clean_db: Engine,
        alembic_cfg,  # type: ignore[no-untyped-def]
    ) -> None:
        """Full round-trip: upgrade to head, downgrade to 004 (below
        both seed migrations), upgrade back.  Final state must match
        the first upgrade's state exactly — same IDs, same outbox UUIDs.
        """
        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            before_ids = sorted(r[0] for r in conn.execute(sa.text("SELECT id FROM outbox_events WHERE aggregate_type='category'")).fetchall())

        _downgrade_to(alembic_cfg, "004")

        with clean_db.connect() as conn:
            after_downgrade_cats = conn.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar()
            after_downgrade_outbox = conn.execute(
                sa.text("SELECT COUNT(*) FROM outbox_events WHERE aggregate_type='category'")
            ).scalar()
        assert after_downgrade_cats == 0
        assert after_downgrade_outbox == 0

        _upgrade_head(alembic_cfg)

        with clean_db.connect() as conn:
            after_ids = sorted(r[0] for r in conn.execute(sa.text("SELECT id FROM outbox_events WHERE aggregate_type='category'")).fetchall())

        assert before_ids == after_ids, (
            "Deterministic UUIDs should produce byte-identical outbox "
            "row IDs across upgrade/downgrade cycles."
        )


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
