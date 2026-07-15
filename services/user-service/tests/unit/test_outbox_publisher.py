"""Worker tests, repointed at the shared finans-tracker-messaging worker.

The poll/publish/backoff implementation moved to ``messaging``; these
tests exercise it exactly as user-service wires it up in
``app.workers.outbox_publisher`` (default per-entry commit, retry
forever) so the service keeps regression coverage of its own event path.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from messaging import OutboxEntry, OutboxPublisherWorker, compute_backoff

MAX_BACKOFF_S = 300
NOW = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)


def _make_entry(
    entry_id: str = "abc-123",
    event_type: str = "user.created",
    attempts: int = 0,
    payload: str = '{"event_type":"user.created","user_id":1}',
) -> OutboxEntry:
    return OutboxEntry(
        id=entry_id,
        aggregate_type="user",
        aggregate_id="1",
        event_type=event_type,
        payload_json=payload,
        correlation_id="corr-1",
        status="pending",
        attempts=attempts,
        next_attempt_at=NOW,
        created_at=NOW,
    )


def _session_ctx(mock_session: AsyncMock) -> AsyncMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _make_worker(mock_session: AsyncMock, mock_repo: AsyncMock, publisher: AsyncMock) -> OutboxPublisherWorker:
    return OutboxPublisherWorker(
        session_factory=lambda: _session_ctx(mock_session),
        repository_or_model=lambda session: mock_repo,
        publisher=publisher,
        poll_interval=0.01,
        batch_size=5,
    )


@pytest.fixture()
def publisher() -> AsyncMock:
    return AsyncMock()


class TestProcessBatch:
    @pytest.mark.asyncio()
    async def test_publishes_pending_events(self, publisher: AsyncMock) -> None:
        entry = _make_entry()
        mock_repo = AsyncMock()
        mock_repo.fetch_pending.side_effect = [[entry], []]
        mock_session = AsyncMock()

        worker = _make_worker(mock_session, mock_repo, publisher)
        count = await worker._process_batch()

        assert count == 1
        publisher.publish_raw.assert_awaited_once()
        mock_repo.mark_published.assert_awaited_once_with("abc-123")
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_empty_outbox_returns_zero(self, publisher: AsyncMock) -> None:
        mock_repo = AsyncMock()
        mock_repo.fetch_pending.return_value = []
        mock_session = AsyncMock()

        worker = _make_worker(mock_session, mock_repo, publisher)
        count = await worker._process_batch()

        assert count == 0
        publisher.publish_raw.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_publish_failure_records_failure_for_retry(self, publisher: AsyncMock) -> None:
        entry = _make_entry(attempts=2)
        mock_repo = AsyncMock()
        mock_repo.fetch_pending.side_effect = [[entry], []]
        publisher.publish_raw.side_effect = RuntimeError("broker down")
        mock_session = AsyncMock()

        worker = _make_worker(mock_session, mock_repo, publisher)
        count = await worker._process_batch()

        assert count == 1
        mock_repo.mark_published.assert_not_awaited()
        # retry-forever wiring: max_attempts=None, backoff computed in repo
        mock_repo.record_failure.assert_awaited_once_with(entry, max_attempts=None)


class TestBackoffCalculation:
    def test_exponential_backoff_capped(self) -> None:
        for attempts in range(10):
            assert compute_backoff(attempts) <= MAX_BACKOFF_S

    def test_first_retry_is_five_seconds(self) -> None:
        assert compute_backoff(0) == 5

    def test_third_retry_is_twenty_seconds(self) -> None:
        assert compute_backoff(2) == 20


class TestWorkerShim:
    def test_shim_wires_service_model_and_session_factory(self) -> None:
        """The compose entrypoint module must keep exposing ``main`` and
        wire the shared worker with this service's model + session factory.
        """
        os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        os.environ.setdefault("JWT_SECRET", "test-secret")

        import inspect

        from app.workers import outbox_publisher as shim

        assert inspect.iscoroutinefunction(shim.main)
        assert shim.OutboxEventModel.__tablename__ == "outbox_events"
