"""Integration test: run alembic upgrade head against a real Postgres.

Verifies that all tables exist and seed data is populated correctly.
Requires Docker to be running (testcontainers spins up a Postgres).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


def _bind_app_session_factory_to(async_url: str):
    """Point app code at the Testcontainer, whatever imported first.

    ``app.database`` builds its engine at import time from settings, so setting
    DATABASE_URL only works while nothing has imported it yet. Any test module
    that imports ``app.main`` during collection — most of tests/integration —
    freezes the factory on localhost:5432, and a test using app code then fails
    only when run alongside them. Rebinding makes the outcome independent of
    collection order instead of passing in isolation and failing in CI.
    """
    import app.database as app_database

    previous_engine = app_database.engine
    previous_factory = app_database.async_session_factory
    container_engine = create_async_engine(async_url, echo=False)
    container_factory = async_sessionmaker(container_engine, class_=AsyncSession, expire_on_commit=False)
    app_database.engine = container_engine
    app_database.async_session_factory = container_factory

    # Modules that already did ``from app.database import async_session_factory``
    # hold their own binding, so patch those too.
    rebound = []
    for name, module in list(sys.modules.items()):
        if name.startswith("app.") and getattr(module, "async_session_factory", None) is previous_factory:
            module.async_session_factory = container_factory
            rebound.append(module)

    def restore() -> None:
        for module in rebound:
            module.async_session_factory = previous_factory
        app_database.engine = previous_engine
        app_database.async_session_factory = previous_factory
        asyncio.run(container_engine.dispose())

    return restore


@pytest.fixture(scope="module")
def engine(postgres):
    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ["DATABASE_URL"] = async_url
    restore_app_session_factory = _bind_app_session_factory_to(async_url)

    eng = create_engine(url)

    for _ in range(30):
        try:
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except OperationalError:
            time.sleep(1)
    else:
        raise RuntimeError("Postgres Testcontainer did not become ready in time")

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")

    try:
        yield eng
    finally:
        restore_app_session_factory()
        eng.dispose()


class TestTablesExist:
    EXPECTED_TABLES = [
        "categories",
        "subcategories",
        "merchants",
        "categorization_rules",
        "categorization_results",
        "outbox_events",
        "processed_events",
    ]

    def test_all_tables_created(self, engine) -> None:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        for expected in self.EXPECTED_TABLES:
            assert expected in tables, f"Table '{expected}' not found. Got: {tables}"


class TestCategorySeed:
    def test_legacy_and_target_categories_seeded(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM categories")).scalar()
            assert count == 23

    def test_category_ids_pinned(self, engine) -> None:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name FROM categories WHERE id <= 10 ORDER BY id")).fetchall()
            assert rows[0] == (1, "Mad & drikke")
            assert rows[-1] == (10, "Overfoersler")

    def test_category_sequence_synced(self, engine) -> None:
        with engine.connect() as conn:
            next_val = conn.execute(text("SELECT nextval('categories_id_seq')")).scalar()
            assert next_val > 10, f"Sequence should be >10 after seed, got {next_val}"

    def test_taxonomy_surrogate_ledger_is_complete(self, engine) -> None:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT node_kind,COUNT(*) FROM taxonomy_surrogate_allocations "
                    "GROUP BY node_kind ORDER BY node_kind"
                )
            ).fetchall()
            assert rows == [("category", 13), ("subcategory", 67)]

    def test_display_order_matches_canonical_seed(self, engine) -> None:
        """Migration 006 heals display_order=0 drift left by the old
        CategorySyncConsumer — after upgrade the canonical ordering from
        migration 002 must hold."""
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, display_order FROM categories WHERE id <= 10 ORDER BY id")).fetchall()
            expected = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 10, 10: 20}
            assert dict(rows) == expected


class TestSubcategorySeed:
    def test_legacy_and_target_subcategories_seeded(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM subcategories")).scalar()
            assert count == 108

    def test_subcategory_ids_pinned(self, engine) -> None:
        with engine.connect() as conn:
            dagligvarer = conn.execute(
                text("SELECT id, category_id FROM subcategories WHERE name = 'Dagligvarer'")
            ).fetchone()
            assert dagligvarer is not None
            assert dagligvarer.id == 1
            assert dagligvarer.category_id == 1

            anden = conn.execute(text("SELECT id, category_id FROM subcategories WHERE name = 'Anden'")).fetchone()
            assert anden is not None
            assert anden.id == 32
            assert anden.category_id == 8

    def test_subcategory_sequence_synced(self, engine) -> None:
        with engine.connect() as conn:
            next_val = conn.execute(text("SELECT nextval('subcategories_id_seq')")).scalar()
            assert next_val > 41, f"Sequence should be >41 after seed, got {next_val}"


class TestMerchantSeed:
    def test_merchants_seeded(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM merchants")).scalar()
            assert count == 166, f"Expected 130 legacy plus 36 canonical merchants, got {count}"

    def test_merchant_references_valid_subcategory(self, engine) -> None:
        with engine.connect() as conn:
            orphans = conn.execute(
                text(
                    "SELECT m.normalized_name FROM merchants m "
                    "LEFT JOIN subcategories s ON m.subcategory_id = s.id "
                    "WHERE s.id IS NULL AND m.merchant_key IS NULL"
                )
            ).fetchall()
            assert orphans == [], f"Merchants with invalid subcategory_id: {orphans}"

    def test_netto_maps_to_dagligvarer(self, engine) -> None:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT m.normalized_name, s.name AS subcategory "
                    "FROM merchants m "
                    "JOIN subcategories s ON m.subcategory_id = s.id "
                    "WHERE m.normalized_name = 'netto'"
                )
            ).fetchone()
            assert row is not None
            assert row.subcategory == "Dagligvarer"


class TestRuleSeed:
    def test_rules_seeded(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM categorization_rules")).scalar()
            assert count == 212, f"Expected 130 legacy plus 82 target rules, got {count}"

    def test_all_rules_are_system_rules(self, engine) -> None:
        with engine.connect() as conn:
            user_rules = conn.execute(
                text("SELECT COUNT(*) FROM categorization_rules WHERE user_id IS NOT NULL")
            ).scalar()
            assert user_rules == 0

    def test_target_rules_have_supported_pattern_types(self, engine) -> None:
        with engine.connect() as conn:
            non_keyword = conn.execute(
                text(
                    "SELECT COUNT(*) FROM categorization_rules "
                    "WHERE rule_key IS NOT NULL AND pattern_type NOT IN ('keyword', 'merchant')"
                )
            ).scalar()
            assert non_keyword == 0

    def test_rules_reference_valid_subcategories(self, engine) -> None:
        with engine.connect() as conn:
            orphans = conn.execute(
                text(
                    "SELECT r.pattern_value FROM categorization_rules r "
                    "LEFT JOIN subcategories s ON r.matches_subcategory_id = s.id "
                    "WHERE s.id IS NULL"
                )
            ).fetchall()
            assert orphans == [], f"Rules with invalid subcategory_id: {orphans}"

    def test_system_rules_have_priority_100(self, engine) -> None:
        with engine.connect() as conn:
            distinct = conn.execute(
                text("SELECT DISTINCT priority FROM categorization_rules WHERE user_id IS NULL")
            ).fetchall()
            priorities = [row[0] for row in distinct]
            assert priorities == [100], f"Expected all system rules at priority 100, got {priorities}"

    def test_tax06_target_state_is_additive_and_canonical(self, engine) -> None:
        with engine.connect() as conn:
            active_categories = conn.execute(
                text("SELECT COUNT(*) FROM categories WHERE semantic_key IS NOT NULL AND lifecycle='active'")
            ).scalar()
            active_subcategories = conn.execute(
                text("SELECT COUNT(*) FROM subcategories WHERE semantic_key IS NOT NULL AND lifecycle='active'")
            ).scalar()
            deprecated_legacy = conn.execute(
                text(
                    "SELECT (SELECT COUNT(*) FROM categories WHERE semantic_key IS NULL AND lifecycle='deprecated') + "
                    "(SELECT COUNT(*) FROM subcategories WHERE semantic_key IS NULL AND lifecycle='deprecated')"
                )
            ).scalar()
            active_rules = conn.execute(
                text("SELECT COUNT(*) FROM categorization_rules WHERE rule_key IS NOT NULL AND active")
            ).scalar()
            legacy_active = conn.execute(
                text("SELECT COUNT(*) FROM categorization_rules WHERE rule_key IS NULL AND user_id IS NULL AND active")
            ).scalar()
            assert (active_categories, active_subcategories, deprecated_legacy) == (13, 67, 51)
            assert (active_rules, legacy_active) == (82, 0)


class TestInfrastructureTables:
    def test_outbox_holds_exactly_the_taxonomy_seed_events(self, engine) -> None:
        """Migration 006 re-announces the seed taxonomy (10 categories +
        41 subcategories) as pending outbox events for downstream read
        copies — nothing else may be in the outbox after upgrade."""
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT event_type, COUNT(*) FROM outbox_events GROUP BY event_type")).fetchall()
            counts = dict(rows)
            assert counts == {"category.created": 23, "subcategory.created": 108}
            pending = conn.execute(text("SELECT COUNT(*) FROM outbox_events WHERE status = 'pending'")).scalar()
            assert pending == 131

    def test_processed_events_is_empty(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM processed_events")).scalar()
            assert count == 0

    def test_categorization_results_is_empty(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM categorization_results")).scalar()
            assert count == 0


class TestUserRulesUniqueIndex:
    """Migration 007 — partial unique index backing user-rule upserts
    (feedback loop) and duplicate guards (rules API)."""

    def test_index_is_unique_and_partial(self, engine) -> None:
        with engine.connect() as conn:
            indexdef = conn.execute(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_rules_user_pattern'")
            ).scalar()
            assert indexdef is not None, "uq_rules_user_pattern missing"
            assert "UNIQUE" in indexdef
            assert "user_id IS NOT NULL" in indexdef

    def test_duplicate_user_rule_rejected_but_seed_rules_exempt(self, engine) -> None:
        from sqlalchemy.exc import IntegrityError

        with engine.connect() as conn:
            sub_id = conn.execute(text("SELECT id FROM subcategories LIMIT 1")).scalar()
            insert = text(
                "INSERT INTO categorization_rules "
                "(user_id, priority, pattern_type, pattern_value, matches_subcategory_id, active, created_at) "
                "VALUES (:uid, 50, 'keyword', 'uq-test-pattern', :sub, true, now())"
            )
            conn.execute(insert, {"uid": 91001, "sub": sub_id})
            conn.commit()
            try:
                with pytest.raises(IntegrityError):
                    conn.execute(insert, {"uid": 91001, "sub": sub_id})
                    conn.commit()
                conn.rollback()

                # NULL user_id is exempt (seeds may repeat patterns)
                seed_insert = text(
                    "INSERT INTO categorization_rules "
                    "(user_id, priority, pattern_type, pattern_value, matches_subcategory_id, active, created_at) "
                    "VALUES (NULL, 100, 'keyword', 'uq-test-pattern', :sub, true, now())"
                )
                conn.execute(seed_insert, {"sub": sub_id})
                conn.execute(seed_insert, {"sub": sub_id})
                conn.commit()
            finally:
                conn.execute(text("DELETE FROM categorization_rules WHERE pattern_value = 'uq-test-pattern'"))
                conn.commit()


class TestTaxonomyRepair:
    def test_same_run_id_is_idempotent(self, engine) -> None:
        from app.tools.repair_taxonomy import enqueue_repair

        async def run_twice() -> tuple[int, int]:
            return (
                await enqueue_repair("migration-test-repair"),
                await enqueue_repair("migration-test-repair"),
            )

        first, second = asyncio.run(run_twice())
        assert (first, second) == (80, 0)
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM outbox_events WHERE payload_json::jsonb ->> 'event_version' = '3'")
            ).scalar()
            assert count == 160

    def test_forward_repair_roundtrip_restores_target_state(self, engine) -> None:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
        command.downgrade(config, "007")
        command.upgrade(config, "head")

        with engine.connect() as conn:
            counts = conn.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM categories WHERE semantic_key IS NOT NULL), "
                    "(SELECT COUNT(*) FROM subcategories WHERE semantic_key IS NOT NULL), "
                    "(SELECT COUNT(*) FROM categorization_rules WHERE rule_key IS NOT NULL)"
                )
            ).one()
            assert counts == (13, 67, 82)


def test_populated_007_collision_bootstrap_preserves_existing_references() -> None:
    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url()
        async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
        os.environ["DATABASE_URL"] = async_url
        engine = create_engine(url)
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "007")
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO categories (id,name,type,display_order) VALUES (11,'Snapshot category','expense',99)")
            )
            conn.execute(
                text(
                    "INSERT INTO subcategories (id,name,category_id,is_default) "
                    "VALUES (42,'Snapshot subcategory',11,true)"
                )
            )
            merchant_id = conn.execute(
                text(
                    "INSERT INTO merchants (normalized_name,display_name,subcategory_id) "
                    "VALUES ('snapshot merchant','Snapshot merchant',42) RETURNING id"
                )
            ).scalar_one()
            rule_id = conn.execute(
                text(
                    "INSERT INTO categorization_rules "
                    "(user_id,priority,pattern_type,pattern_value,matches_subcategory_id,active) "
                    "VALUES (1234,50,'keyword','snapshot rule',42,true) RETURNING id"
                )
            ).scalar_one()
            result_id = conn.execute(
                text(
                    "INSERT INTO categorization_results "
                    "(transaction_id,category_id,subcategory_id,merchant_id,tier,confidence,model_version) "
                    "VALUES (999,11,42,:merchant_id,'manual','high','snapshot') RETURNING id"
                ),
                {"merchant_id": merchant_id},
            ).scalar_one()

        from app.tools.tax06_collision_bootstrap import bootstrap

        starts = bootstrap(engine, "p244-populated-snapshot")
        assert starts == (24, 109)
        assert bootstrap(engine, "p244-populated-snapshot") == starts
        with pytest.raises(RuntimeError, match="does not own existing allocation ledger"):
            bootstrap(engine, "different-change")
        command.upgrade(config, "head")

        with engine.connect() as conn:
            assert conn.execute(text("SELECT name,type,display_order FROM categories WHERE id=11")).one() == (
                "Snapshot category",
                "expense",
                99,
            )
            assert conn.execute(text("SELECT name,category_id,is_default FROM subcategories WHERE id=42")).one() == (
                "Snapshot subcategory",
                11,
                True,
            )
            assert (
                conn.execute(
                    text("SELECT subcategory_id FROM merchants WHERE id=:id"), {"id": merchant_id}
                ).scalar_one()
                == 42
            )
            assert (
                conn.execute(
                    text("SELECT matches_subcategory_id FROM categorization_rules WHERE id=:id"), {"id": rule_id}
                ).scalar_one()
                == 42
            )
            assert conn.execute(
                text("SELECT category_id,subcategory_id,merchant_id FROM categorization_results WHERE id=:id"),
                {"id": result_id},
            ).one() == (11, 42, merchant_id)
            assert conn.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM categories WHERE semantic_key IS NOT NULL),"
                    "(SELECT COUNT(*) FROM subcategories WHERE semantic_key IS NOT NULL),"
                    "(SELECT COUNT(*) FROM taxonomy_surrogate_allocations)"
                )
            ).one() == (13, 67, 80)
        engine.dispose()
