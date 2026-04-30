"""Integration test: run alembic upgrade head against a real Postgres.

Verifies that all tables exist and seed data is populated correctly.
Requires Docker to be running (testcontainers spins up a Postgres).
"""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def engine(postgres):
    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ["DATABASE_URL"] = async_url

    eng = create_engine(url)

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")

    return eng


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
    def test_ten_categories_seeded(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM categories")).scalar()
            assert count == 10

    def test_category_ids_pinned(self, engine) -> None:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name FROM categories ORDER BY id")).fetchall()
            assert rows[0] == (1, "Mad & drikke")
            assert rows[-1] == (10, "Overfoersler")

    def test_category_sequence_synced(self, engine) -> None:
        with engine.connect() as conn:
            next_val = conn.execute(text("SELECT nextval('categories_id_seq')")).scalar()
            assert next_val > 10, f"Sequence should be >10 after seed, got {next_val}"


class TestSubcategorySeed:
    def test_41_subcategories_seeded(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM subcategories")).scalar()
            assert count == 41

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
            assert count > 80, f"Expected 80+ merchants from SEED_MERCHANT_MAPPINGS, got {count}"

    def test_merchant_references_valid_subcategory(self, engine) -> None:
        with engine.connect() as conn:
            orphans = conn.execute(
                text(
                    "SELECT m.normalized_name FROM merchants m "
                    "LEFT JOIN subcategories s ON m.subcategory_id = s.id "
                    "WHERE s.id IS NULL"
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
            assert count > 80, f"Expected 80+ rules from SEED_MERCHANT_MAPPINGS, got {count}"

    def test_all_rules_are_system_rules(self, engine) -> None:
        with engine.connect() as conn:
            user_rules = conn.execute(
                text("SELECT COUNT(*) FROM categorization_rules WHERE user_id IS NOT NULL")
            ).scalar()
            assert user_rules == 0

    def test_all_rules_are_keyword_type(self, engine) -> None:
        with engine.connect() as conn:
            non_keyword = conn.execute(
                text("SELECT COUNT(*) FROM categorization_rules WHERE pattern_type != 'keyword'")
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


class TestInfrastructureTables:
    def test_outbox_is_empty(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM outbox_events")).scalar()
            assert count == 0

    def test_processed_events_is_empty(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM processed_events")).scalar()
            assert count == 0

    def test_categorization_results_is_empty(self, engine) -> None:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM categorization_results")).scalar()
            assert count == 0
