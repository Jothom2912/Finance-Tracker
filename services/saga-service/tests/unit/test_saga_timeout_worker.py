from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.workers.saga_timeout_worker import SagaTimeoutWorker


@pytest.mark.asyncio
async def test_check_once_calls_orchestrator_with_configured_max_age() -> None:
    registry = MagicMock()
    worker = SagaTimeoutWorker(
        registry,
        interval_seconds=30,
        timeout_seconds=300,
    )

    mock_orchestrator = AsyncMock()
    mock_orchestrator.check_timeouts.return_value = []

    with patch("app.workers.saga_timeout_worker.async_session_factory") as session_factory:
        session = AsyncMock()
        session_factory.return_value.__aenter__.return_value = session
        with patch("app.workers.saga_timeout_worker.SagaOrchestrator", return_value=mock_orchestrator):
            await worker._check_once()

    mock_orchestrator.check_timeouts.assert_awaited_once_with(timedelta(seconds=300))
