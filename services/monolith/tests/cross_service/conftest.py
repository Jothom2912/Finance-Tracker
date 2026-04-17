"""Fixtures for live cross-service parity tests.

These tests run against the running ``docker compose`` environment —
not Testcontainers — because their whole purpose is to catch runtime
state drift between the monolith's MySQL ``Category`` projection and
transaction-service's Postgres ``categories`` source of truth.  A
hermetic test environment that seeds both sides consistently would
miss exactly the class of bug this suite exists to prevent.

Connection details match ``docker-compose.yml`` verbatim (port 3307
for MySQL, 5434 for Postgres).  When either database is unreachable
we skip the whole module rather than erroring — developers without
the compose stack running should not be blocked.

Run manually with ``make test-cross-service`` from
``services/monolith/``, or opt in from CI once a compose-backed job
is added.  The default ``make test`` target intentionally does *not*
include this subdir.
"""

from __future__ import annotations

import pytest
import pymysql
import psycopg2

_MYSQL_CONN_KWARGS = dict(
    host="localhost",
    port=3307,
    user="root",
    password="root",
    database="finans_tracker",
    connect_timeout=2,
)

_POSTGRES_CONN_KWARGS = dict(
    host="localhost",
    port=5434,
    user="transaction_service",
    password="transaction_service_pass",
    dbname="transactions",
    connect_timeout=2,
)


def _mysql_reachable() -> tuple[bool, str]:
    try:
        conn = pymysql.connect(**_MYSQL_CONN_KWARGS)  # type: ignore[arg-type]
        conn.close()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _postgres_reachable() -> tuple[bool, str]:
    try:
        conn = psycopg2.connect(**_POSTGRES_CONN_KWARGS)
        conn.close()
        return True, ""
    except Exception as exc:
        return False, str(exc)


_mysql_ok, _mysql_err = _mysql_reachable()
_pg_ok, _pg_err = _postgres_reachable()

if not _mysql_ok or not _pg_ok:
    reasons = []
    if not _mysql_ok:
        reasons.append(f"MySQL on :3307 unreachable ({_mysql_err})")
    if not _pg_ok:
        reasons.append(f"Postgres on :5434 unreachable ({_pg_err})")
    pytest.skip(
        "Live cross-service tests require the docker-compose stack "
        "to be running. Skipping because: " + "; ".join(reasons),
        allow_module_level=True,
    )


@pytest.fixture
def mysql_conn():  # type: ignore[no-untyped-def]
    conn = pymysql.connect(**_MYSQL_CONN_KWARGS)  # type: ignore[arg-type]
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def postgres_conn():  # type: ignore[no-untyped-def]
    conn = psycopg2.connect(**_POSTGRES_CONN_KWARGS)
    try:
        yield conn
    finally:
        conn.close()
