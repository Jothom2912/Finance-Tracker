"""OutboxRepository behaviour on sqlite+aiosqlite.

FOR UPDATE SKIP LOCKED is silently dropped by the SQLite dialect, so
locking semantics are NOT covered here (PostgreSQL-only path); these
tests cover predicates, ordering, limits and status transitions.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from messaging.outbox import (
    MAX_BACKOFF_S,
    OutboxRepository,
    OutboxStatus,
    compute_backoff,
)
from messaging.time import utcnow_naive
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeEvent, OutboxEventModel


@pytest.fixture
def repo(session: AsyncSession) -> OutboxRepository:
    return OutboxRepository(session, OutboxEventModel)


async def _get(session: AsyncSession, event_id: str) -> OutboxEventModel:
    result = await session.execute(
        select(OutboxEventModel).where(OutboxEventModel.id == event_id)
    )
    return result.scalar_one()


class TestAdd:
    async def test_add_creates_pending_row(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        event = FakeEvent("user.created", user_id=7)
        await repo.add(event, aggregate_type="user", aggregate_id="7")

        rows = (await session.execute(select(OutboxEventModel))).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.status == OutboxStatus.PENDING
        assert row.attempts == 0
        assert row.event_type == "user.created"
        assert row.aggregate_type == "user"
        assert row.aggregate_id == "7"
        assert row.correlation_id == event.correlation_id
        assert row.payload_json == event.to_json()

    async def test_add_batch_inserts_all(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        events = [FakeEvent(f"thing.evt{i}") for i in range(3)]
        await repo.add_batch(events, aggregate_type="thing", aggregate_id="1")

        rows = (await session.execute(select(OutboxEventModel))).scalars().all()
        assert len(rows) == 3
        assert {r.event_type for r in rows} == {"thing.evt0", "thing.evt1", "thing.evt2"}


class TestFetchPending:
    async def test_returns_pending_and_failed_due_now(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        await repo.add(FakeEvent("a.one"), "a", "1")
        await repo.add(FakeEvent("a.two"), "a", "2")
        rows = (await session.execute(select(OutboxEventModel))).scalars().all()
        failed = rows[0]
        failed.status = OutboxStatus.FAILED
        failed.next_attempt_at = utcnow_naive() - timedelta(seconds=1)
        await session.flush()

        entries = await repo.fetch_pending(batch_size=10)
        assert {e.event_type for e in entries} == {"a.one", "a.two"}

    async def test_excludes_future_published_and_dead(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        for name in ("future", "published", "dead", "due"):
            await repo.add(FakeEvent(f"x.{name}"), "x", name)
        rows = (await session.execute(select(OutboxEventModel))).scalars().all()
        by_type = {r.event_type: r for r in rows}
        by_type["x.future"].status = OutboxStatus.FAILED
        by_type["x.future"].next_attempt_at = utcnow_naive() + timedelta(minutes=5)
        by_type["x.published"].status = OutboxStatus.PUBLISHED
        by_type["x.dead"].status = OutboxStatus.DEAD
        await session.flush()

        entries = await repo.fetch_pending(batch_size=10)
        assert [e.event_type for e in entries] == ["x.due"]

    async def test_orders_by_created_at_and_respects_limit(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        base = utcnow_naive() - timedelta(minutes=10)
        for i in range(5):
            await repo.add(FakeEvent(f"o.e{i}"), "o", str(i))
        rows = (await session.execute(select(OutboxEventModel))).scalars().all()
        # Assign distinct created_at values in reverse insertion order
        for i, row in enumerate(sorted(rows, key=lambda r: r.event_type, reverse=True)):
            row.created_at = base + timedelta(seconds=i)
        await session.flush()

        entries = await repo.fetch_pending(batch_size=3)
        assert [e.event_type for e in entries] == ["o.e4", "o.e3", "o.e2"]


class TestStatusTransitions:
    async def test_mark_published(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        await repo.add(FakeEvent(), "t", "1")
        entry = (await repo.fetch_pending())[0]

        await repo.mark_published(entry.id)

        row = await _get(session, entry.id)
        assert row.status == OutboxStatus.PUBLISHED
        assert row.published_at is not None

    async def test_mark_failed_increments_attempts_and_sets_next_attempt(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        await repo.add(FakeEvent(), "t", "1")
        entry = (await repo.fetch_pending())[0]
        next_at = utcnow_naive() + timedelta(seconds=5)

        await repo.mark_failed(entry.id, next_at)

        row = await _get(session, entry.id)
        assert row.status == OutboxStatus.FAILED
        assert row.attempts == 1
        assert row.next_attempt_at == next_at

    async def test_record_failure_uses_legacy_backoff_formula(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        await repo.add(FakeEvent(), "t", "1")
        entry = (await repo.fetch_pending())[0]

        before = utcnow_naive()
        next_at = await repo.record_failure(entry)

        assert next_at is not None
        expected_backoff = compute_backoff(entry.attempts)  # attempts=0 → 5s
        assert expected_backoff == 5
        assert timedelta(seconds=expected_backoff - 1) <= (next_at - before) <= timedelta(
            seconds=expected_backoff + 1
        )
        row = await _get(session, entry.id)
        assert row.status == OutboxStatus.FAILED
        assert row.attempts == 1

    async def test_record_failure_marks_dead_at_max_attempts(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        await repo.add(FakeEvent(), "t", "1")
        row = (await session.execute(select(OutboxEventModel))).scalar_one()
        row.attempts = 2
        await session.flush()
        entry = (await repo.fetch_pending())[0]

        next_at = await repo.record_failure(entry, max_attempts=3)

        assert next_at is None
        row = await _get(session, entry.id)
        assert row.status == OutboxStatus.DEAD
        assert row.attempts == 3
        # Dead rows are terminal — never polled again
        assert await repo.fetch_pending() == []

    async def test_record_failure_below_max_attempts_stays_failed(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        await repo.add(FakeEvent(), "t", "1")
        entry = (await repo.fetch_pending())[0]

        next_at = await repo.record_failure(entry, max_attempts=3)

        assert next_at is not None
        row = await _get(session, entry.id)
        assert row.status == OutboxStatus.FAILED


class TestPurgePublished:
    async def test_purges_only_old_published_rows(
        self, repo: OutboxRepository, session: AsyncSession
    ) -> None:
        for name in ("old_published", "new_published", "pending"):
            await repo.add(FakeEvent(f"p.{name}"), "p", name)
        rows = (await session.execute(select(OutboxEventModel))).scalars().all()
        by_type = {r.event_type: r for r in rows}
        by_type["p.old_published"].status = OutboxStatus.PUBLISHED
        by_type["p.old_published"].published_at = utcnow_naive() - timedelta(days=10)
        by_type["p.new_published"].status = OutboxStatus.PUBLISHED
        by_type["p.new_published"].published_at = utcnow_naive() - timedelta(days=1)
        await session.flush()

        deleted = await repo.purge_published(older_than_days=7)

        assert deleted == 1
        remaining = (await session.execute(select(OutboxEventModel))).scalars().all()
        assert {r.event_type for r in remaining} == {"p.new_published", "p.pending"}


class TestBackoffFormula:
    def test_matches_legacy_values(self) -> None:
        assert [compute_backoff(n) for n in range(7)] == [5, 10, 20, 40, 80, 160, 300]

    def test_caps_at_max(self) -> None:
        assert compute_backoff(100) == MAX_BACKOFF_S
