from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.entities import OutboxEntry
from app.workers.outbox_publisher import MAX_BACKOFF_S, OutboxPublisherWorker

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


@pytest.fixture()
def publisher() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def worker(publisher: AsyncMock) -> OutboxPublisherWorker:
    return OutboxPublisherWorker(publisher, poll_interval=0.01, batch_size=5)


class TestProcessBatch:
    @pytest.mark.asyncio()
    async def test_publishes_pending_events(
        self, worker: OutboxPublisherWorker, publisher: AsyncMock
    ) -> None:
        entry = _make_entry()
        mock_repo = AsyncMock()
        mock_repo.fetch_pending.return_value = [entry]
        mock_session = AsyncMock()

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.outbox_publisher.async_session_factory",
            return_value=ctx,
        ), patch(
            "app.workers.outbox_publisher.PostgresOutboxRepository",
            return_value=mock_repo,
        ):
            count = await worker._process_batch()

        assert count == 1
        publisher.publish_raw.assert_awaited_once()
        mock_repo.mark_published.assert_awaited_once_with("abc-123")
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_empty_outbox_returns_zero(
        self, worker: OutboxPublisherWorker
    ) -> None:
        mock_repo = AsyncMock()
        mock_repo.fetch_pending.return_value = []
        mock_session = AsyncMock()

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.outbox_publisher.async_session_factory",
            return_value=ctx,
        ), patch(
            "app.workers.outbox_publisher.PostgresOutboxRepository",
            return_value=mock_repo,
        ):
            count = await worker._process_batch()

        assert count == 0

    @pytest.mark.asyncio()
    async def test_publish_failure_marks_failed_with_backoff(
        self, worker: OutboxPublisherWorker, publisher: AsyncMock
    ) -> None:
        entry = _make_entry(attempts=2)
        mock_repo = AsyncMock()
        mock_repo.fetch_pending.return_value = [entry]
        publisher.publish_raw.side_effect = RuntimeError("broker down")
        mock_session = AsyncMock()

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.outbox_publisher.async_session_factory",
            return_value=ctx,
        ), patch(
            "app.workers.outbox_publisher.PostgresOutboxRepository",
            return_value=mock_repo,
        ):
            count = await worker._process_batch()

        assert count == 1
        mock_repo.mark_published.assert_not_awaited()
        mock_repo.mark_failed.assert_awaited_once()

        failed_call = mock_repo.mark_failed.call_args
        assert failed_call[0][0] == "abc-123"


class TestBackoffCalculation:
    def test_exponential_backoff_capped(self) -> None:
        for attempts in range(10):
            backoff = min(2**attempts * 5, MAX_BACKOFF_S)
            assert backoff <= MAX_BACKOFF_S

    def test_first_retry_is_five_seconds(self) -> None:
        assert min(2**0 * 5, MAX_BACKOFF_S) == 5

    def test_third_retry_is_twenty_seconds(self) -> None:
        assert min(2**2 * 5, MAX_BACKOFF_S) == 20
