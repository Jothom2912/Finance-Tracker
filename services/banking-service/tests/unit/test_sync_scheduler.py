"""Tests for the scheduled bank-sync sweep (F1-05).

``run_once`` testes med patched repo + fake service-factory (banking har
ingen sqlite-kompatible modeller — house style er mock-baserede unit tests;
SQL-semantikken verificeres live).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.domain.entities import BankConnection
from app.domain.exceptions import BankConsentExpired
from app.workers.sync_scheduler import run_once

FROZEN_NOW = datetime(2026, 7, 17, 3, 0, 0, tzinfo=timezone.utc)


def _conn(
    *,
    user_id: int = 2,
    last_synced_hours_ago: float | None = 30,
    expires_at: datetime | None = None,
) -> BankConnection:
    return BankConnection(
        id=uuid4(),
        account_id=1,
        user_id=user_id,
        session_id="sess-1",
        bank_name="Nordea",
        bank_country="DK",
        bank_account_uid="uid-1",
        status="active",
        expires_at=expires_at,
        last_synced_at=(FROZEN_NOW - timedelta(hours=last_synced_hours_ago) if last_synced_hours_ago else None),
    )


class _FakeSessionFactory:
    """Async-context-manager-fabrik; selve sessionen bruges kun af mocks."""

    def __call__(self):
        class _Ctx:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                return None

        return _Ctx()


async def _run(connections, service):
    session_factory = _FakeSessionFactory()
    repo = MagicMock()
    repo.list_active_synced_before = AsyncMock(return_value=connections)
    with patch(
        "app.workers.sync_scheduler.PostgresBankConnectionRepository",
        return_value=repo,
    ):
        return await run_once(
            session_factory,  # type: ignore[arg-type]
            FROZEN_NOW,
            lambda _session: service,
            every_hours=24,
            consent_warn_days=7,
        )


@pytest.mark.asyncio
async def test_due_connection_synced_with_row_user_id_and_no_token() -> None:
    conn = _conn(user_id=42, last_synced_hours_ago=30)
    service = MagicMock()
    service.start_sync_saga = AsyncMock(return_value=("saga-1", False))

    counts = await _run([conn], service)

    assert counts["started"] == 1
    service.start_sync_saga.assert_awaited_once_with(conn.id, user_id=42, bearer_token=None)


@pytest.mark.asyncio
async def test_never_synced_connection_is_due() -> None:
    conn = _conn(last_synced_hours_ago=None)
    service = MagicMock()
    service.start_sync_saga = AsyncMock(return_value=("saga-1", False))

    counts = await _run([conn], service)

    assert counts == {"due": 1, "started": 1, "already_running": 0, "consent_expired": 0, "failed": 0}


@pytest.mark.asyncio
async def test_fresh_connection_not_due() -> None:
    # Repo-query'en filtrerer i SQL; entity-reglen er anden forsvarslinje.
    conn = _conn(last_synced_hours_ago=2)
    service = MagicMock()
    service.start_sync_saga = AsyncMock()

    counts = await _run([conn], service)

    assert counts["due"] == 0
    service.start_sync_saga.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_consent_skipped_without_saga() -> None:
    conn = _conn(expires_at=FROZEN_NOW - timedelta(days=1))
    service = MagicMock()
    service.start_sync_saga = AsyncMock()

    counts = await _run([conn], service)

    assert counts["consent_expired"] == 1
    assert counts["started"] == 0
    service.start_sync_saga.assert_not_awaited()


@pytest.mark.asyncio
async def test_soon_expiring_consent_still_synced() -> None:
    conn = _conn(expires_at=FROZEN_NOW + timedelta(days=3))
    service = MagicMock()
    service.start_sync_saga = AsyncMock(return_value=("saga-1", False))

    counts = await _run([conn], service)

    assert counts["started"] == 1
    assert counts["consent_expired"] == 0


@pytest.mark.asyncio
async def test_already_running_counted_not_failed() -> None:
    conn = _conn()
    service = MagicMock()
    service.start_sync_saga = AsyncMock(return_value=("running-saga", True))

    counts = await _run([conn], service)

    assert counts["already_running"] == 1
    assert counts["failed"] == 0


@pytest.mark.asyncio
async def test_one_failure_does_not_stop_the_rest() -> None:
    failing, healthy = _conn(), _conn()
    service = MagicMock()
    service.start_sync_saga = AsyncMock(side_effect=[RuntimeError("boom"), ("saga-2", False)])

    counts = await _run([failing, healthy], service)

    assert counts["failed"] == 1
    assert counts["started"] == 1


@pytest.mark.asyncio
async def test_consent_expired_from_use_case_counted() -> None:
    # Backstop: entity-tjekket misser (fx clock-skew) men use casen fanger.
    conn = _conn()
    service = MagicMock()
    service.start_sync_saga = AsyncMock(side_effect=BankConsentExpired(conn.id, None))

    counts = await _run([conn], service)

    assert counts["consent_expired"] == 1
    assert counts["failed"] == 0


# ── entity due-rule ──────────────────────────────────────────────────


def test_is_sync_due_boundaries() -> None:
    never = _conn(last_synced_hours_ago=None)
    stale = _conn(last_synced_hours_ago=25)
    exactly = _conn(last_synced_hours_ago=24)
    fresh = _conn(last_synced_hours_ago=23)

    assert never.is_sync_due(FROZEN_NOW, 24) is True
    assert stale.is_sync_due(FROZEN_NOW, 24) is True
    assert exactly.is_sync_due(FROZEN_NOW, 24) is True
    assert fresh.is_sync_due(FROZEN_NOW, 24) is False


def test_is_sync_due_handles_naive_db_datetime() -> None:
    conn = _conn(last_synced_hours_ago=None)
    conn.last_synced_at = (FROZEN_NOW - timedelta(hours=30)).replace(tzinfo=None)

    assert conn.is_sync_due(FROZEN_NOW, 24) is True
