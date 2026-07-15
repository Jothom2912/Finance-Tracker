"""Repository-level tests for H8 (row locking) and the lean staleness scan.

These tests capture the SQLAlchemy statements the repository issues and
compile them against the PostgreSQL dialect, asserting the emitted SQL —
no database required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from app.adapters.outbound.postgres_saga_repository import PostgresSagaRepository
from sqlalchemy.dialects import postgresql


class CapturingSession:
    """Fake AsyncSession that records executed statements and returns empty results."""

    def __init__(self) -> None:
        self.statements: list = []

    async def execute(self, stmt):  # noqa: ANN001, ANN201 — mimics AsyncSession.execute
        self.statements.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        return result


def _compile(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


@pytest.fixture
def session() -> CapturingSession:
    return CapturingSession()


@pytest.fixture
def repo(session: CapturingSession) -> PostgresSagaRepository:
    return PostgresSagaRepository(session)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_by_id_with_for_update_emits_row_lock(repo, session):
    await repo.get_by_id("some-id", for_update=True)

    sql = _compile(session.statements[0])
    assert "FOR UPDATE" in sql
    assert "saga_instances" in sql


@pytest.mark.asyncio
async def test_get_by_id_without_for_update_does_not_lock(repo, session):
    await repo.get_by_id("some-id")

    sql = _compile(session.statements[0])
    assert "FOR UPDATE" not in sql


@pytest.mark.asyncio
async def test_find_stale_ids_selects_only_ids_in_single_query(repo, session):
    await repo.find_stale_ids(older_than=datetime.now(timezone.utc))

    # One statement total: no per-saga step queries.
    assert len(session.statements) == 1
    sql = _compile(session.statements[0])
    # Only the id column is projected — no context_json blob, no step join.
    select_clause = sql.split("FROM")[0]
    assert "saga_instances.id" in select_clause
    assert "context_json" not in select_clause
    assert "saga_step_log" not in sql
    # Still filters on active statuses + staleness.
    assert "status IN" in sql
    assert "updated_at" in sql


@pytest.mark.asyncio
async def test_find_stale_ids_does_not_lock(repo, session):
    """The scan is deliberately lock-free; locking happens per-saga via
    get_by_id(for_update=True) with re-validation."""
    await repo.find_stale_ids(older_than=datetime.now(timezone.utc))

    sql = _compile(session.statements[0])
    assert "FOR UPDATE" not in sql
