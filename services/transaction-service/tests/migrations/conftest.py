"""Shared fixtures for Alembic migration tests.

The rest of the test suite uses SQLite in-memory for speed — fine for
unit tests but useless for verifying migrations, which carry
Postgres-specific SQL (``ON CONFLICT``, ``setval``, ``uuid`` handling).
This subsuite instead spins up a real Postgres container per test
session via Testcontainers, runs Alembic against it, and exercises
the migrations as they'd run in production.

Fixtures are ``session``-scoped so the container boots exactly once
for the whole migration suite (~5-15s, amortised across all tests in
this file).  Individual tests can still freely migrate up and down —
each test is responsible for leaving the DB in a known state or using
the ``clean_db`` fixture for a fresh starting point.

Requirements:
    * Docker running locally (Testcontainers talks to the Docker
      daemon).  If Docker is missing, every test in this subdir is
      skipped with a pointer to the root cause rather than erroring.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

# Pydantic-settings validates ``Settings()`` at import time, so these
# env vars must exist before anything in ``app.*`` is imported —
# including by fixtures below.  The values are placeholders; the real
# DATABASE_URL is injected per-test by the ``alembic_cfg`` fixture.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://placeholder@localhost/placeholder")
os.environ.setdefault("JWT_SECRET", "migration-test-placeholder-secret")

# Testcontainers' Ryuk reaper container fails to get its port mapping
# on some Docker Desktop setups (observed on Windows).  Disabling it
# means test containers aren't auto-reaped on orphaned test runs,
# which is a fair trade for having the suite run at all; the session-
# scoped fixture's explicit ``container.stop()`` handles cleanup on
# normal paths.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine


def _docker_available() -> bool:
    try:
        import docker  # type: ignore[import-untyped]
    except ImportError:
        return False
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


if not _docker_available():
    pytest.skip(
        "Docker not reachable — migration tests require Testcontainers. "
        "Start Docker Desktop or use a local docker-compatible runtime "
        "to run this suite.",
        allow_module_level=True,
    )


from testcontainers.postgres import PostgresContainer  # noqa: E402

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _SERVICE_ROOT / "alembic.ini"


@pytest.fixture(scope="session")
def _postgres_container() -> Iterator[PostgresContainer]:
    """Boot a single Postgres 16 container for the whole test session.

    Matches the ``postgres:16`` image used in docker-compose so
    migrations are validated against the same major version.
    """
    container = PostgresContainer("postgres:16")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture
def pg_url(_postgres_container: PostgresContainer) -> str:
    """Sync SQLAlchemy URL (psycopg2) pointing at the test container."""
    url = _postgres_container.get_connection_url()
    return url.replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture
def pg_async_url(pg_url: str) -> str:
    """Async variant of ``pg_url``.

    ``app.database`` creates an ``AsyncEngine`` from ``settings.DATABASE_URL``
    at import time, so it must be given an async-capable driver URL.
    Alembic's ``env.py`` strips the ``+asyncpg`` back off for the
    synchronous migration run.
    """
    return pg_url.replace("postgresql://", "postgresql+asyncpg://")


@pytest.fixture
def pg_engine(pg_url: str) -> Iterator[Engine]:
    engine = sa.create_engine(pg_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def alembic_cfg(pg_url: str, pg_async_url: str) -> Config:
    """Alembic config pointed at the test container.

    ``env.py`` rewrites ``settings.DATABASE_URL`` onto Alembic's
    ``sqlalchemy.url`` at runtime, so overriding the Config option
    here alone isn't enough — we also have to mutate the already-
    instantiated ``settings`` singleton so env.py picks up the test
    container's URL on every ``command.upgrade`` call.
    """
    import app.config as app_config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_SERVICE_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", pg_url)
    app_config.settings.DATABASE_URL = pg_async_url  # type: ignore[misc]
    os.environ["DATABASE_URL"] = pg_async_url
    return cfg


@pytest.fixture
def clean_db(pg_engine: Engine, alembic_cfg: Config) -> Iterator[Engine]:
    """Drop every public-schema table before handing the DB to the test.

    Between tests we wipe the schema rather than recreating the
    container — faster by ~5s per test while still guaranteeing a
    pristine starting point.
    """
    with pg_engine.begin() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
    yield pg_engine


def upgrade_to_head(cfg: Config) -> None:
    command.upgrade(cfg, "head")


def downgrade_to(cfg: Config, revision: str) -> None:
    command.downgrade(cfg, revision)
