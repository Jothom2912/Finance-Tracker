from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.application.service import BankingService
from app.config import settings
from app.domain.entities import BankConnection
from app.domain.exceptions import BankAccountNotOwned, BankConsentExpired
from contracts.events.bank import BankConnectionCreatedEvent
from contracts.events.saga import BankSyncSagaStartEvent

# Deterministic clock injected into the service (no datetime.now() in tests).
FROZEN_NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def uow() -> MagicMock:
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    mock.commit = AsyncMock()
    mock.accounts = AsyncMock()
    mock.connections = AsyncMock()
    mock.pending_auth = AsyncMock()
    mock.outbox = AsyncMock()
    return mock


@pytest.fixture
def account_port() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def banking_client() -> AsyncMock:
    # AsyncMock: the client port is fully async (httpx.AsyncClient adapter).
    client = AsyncMock()
    client.start_authorization.return_value = {"url": "https://bank.test/auth", "state": "state-1"}
    return client


@pytest.fixture
def service(
    uow: MagicMock,
    account_port: AsyncMock,
    banking_client: AsyncMock,
) -> BankingService:
    return BankingService(
        uow=uow,
        account_port=account_port,
        banking_client=banking_client,
        clock=lambda: FROZEN_NOW,
    )


@pytest.mark.asyncio
async def test_start_connect_raises_when_account_not_owned(
    service: BankingService,
    uow: MagicMock,
    account_port: AsyncMock,
) -> None:
    uow.accounts.get_projection.return_value = None
    account_port.get_owner_user_id.return_value = 99

    with pytest.raises(BankAccountNotOwned):
        await service.start_connect("Nordea", "DK", account_id=1, user_id=2)

    banking_client = service._client
    banking_client.start_authorization.assert_not_called()


@pytest.mark.asyncio
async def test_start_connect_saves_pending_auth_when_owned(
    service: BankingService,
    uow: MagicMock,
) -> None:
    uow.accounts.get_projection.return_value = (2, "Main")

    result = await service.start_connect("Nordea", "DK", account_id=1, user_id=2)

    assert result["state"] == "state-1"
    uow.pending_auth.save.assert_awaited_once()
    saved_expiry = uow.pending_auth.save.await_args.kwargs["expires_at"]
    assert saved_expiry == FROZEN_NOW + timedelta(minutes=settings.PENDING_AUTH_TTL_MINUTES)
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_complete_connect_emits_outbox_event(
    service: BankingService,
    uow: MagicMock,
    banking_client: AsyncMock,
) -> None:
    uow.pending_auth.consume.return_value = (1, 2)
    banking_client.create_session.return_value = {
        "session_id": "sess-1",
        "aspsp": {"name": "Nordea", "country": "DK"},
        "accounts": [{"uid": "uid-1", "account_id": {"iban": "DK123"}}],
    }
    uow.connections.get_active_by_uid.return_value = None

    created = await service.complete_connect("auth-code", "state-1")

    assert len(created) == 1
    uow.outbox.add.assert_awaited_once()
    event = uow.outbox.add.await_args.kwargs["event"]
    assert isinstance(event, BankConnectionCreatedEvent)
    assert event.bank_name == "Nordea"
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_list_connections_raises_when_account_not_owned(
    service: BankingService,
    uow: MagicMock,
    account_port: AsyncMock,
) -> None:
    uow.accounts.get_projection.return_value = None
    account_port.get_owner_user_id.return_value = 99

    with pytest.raises(BankAccountNotOwned):
        await service.list_connections(account_id=1, user_id=2)

    uow.connections.list_by_account.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_connections_returns_connections_when_owned(
    service: BankingService,
    uow: MagicMock,
) -> None:
    connection_id = uuid4()
    conn = BankConnection(
        id=connection_id,
        account_id=1,
        user_id=2,
        session_id="sess-1",
        bank_name="Nordea",
        bank_country="DK",
        bank_account_uid="uid-1",
        bank_account_iban="DK123",
    )
    uow.accounts.get_projection.return_value = (2, "Main")
    uow.connections.list_by_account.return_value = [conn]

    result = await service.list_connections(account_id=1, user_id=2)

    assert len(result) == 1
    assert result[0]["id"] == str(connection_id)
    assert result[0]["iban"] == "DK123"


@pytest.mark.asyncio
async def test_disconnect_raises_when_connection_not_owned(
    service: BankingService,
    uow: MagicMock,
    banking_client: AsyncMock,
) -> None:
    connection_id = uuid4()
    conn = BankConnection(
        id=connection_id,
        account_id=1,
        user_id=2,
        session_id="sess-1",
        bank_name="Nordea",
        bank_country="DK",
        bank_account_uid="uid-1",
    )
    uow.connections.get_by_id.return_value = conn

    with pytest.raises(BankAccountNotOwned):
        await service.disconnect(connection_id, user_id=99)

    banking_client.delete_session.assert_not_called()
    uow.connections.update_status.assert_not_awaited()
    uow.outbox.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_disconnect_succeeds_for_owner(
    service: BankingService,
    uow: MagicMock,
    banking_client: AsyncMock,
) -> None:
    connection_id = uuid4()
    conn = BankConnection(
        id=connection_id,
        account_id=1,
        user_id=2,
        session_id="sess-1",
        bank_name="Nordea",
        bank_country="DK",
        bank_account_uid="uid-1",
    )
    uow.connections.get_by_id.return_value = conn

    result = await service.disconnect(connection_id, user_id=2)

    assert result is True
    banking_client.delete_session.assert_called_once_with("sess-1")
    uow.connections.update_status.assert_awaited_once_with(connection_id, "disconnected")
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_start_sync_saga_emits_bank_sync_start_event(
    service: BankingService,
    uow: MagicMock,
) -> None:
    connection_id = uuid4()
    conn = BankConnection(
        id=connection_id,
        account_id=1,
        user_id=2,
        session_id="sess-1",
        bank_name="Nordea",
        bank_country="DK",
        bank_account_uid="uid-1",
    )
    uow.connections.get_by_id.return_value = conn
    uow.accounts.get_projection.return_value = (2, "Main Account")

    saga_id = await service.start_sync_saga(connection_id, user_id=2)

    assert saga_id
    uow.outbox.add.assert_awaited_once()
    event = uow.outbox.add.await_args.kwargs["event"]
    assert isinstance(event, BankSyncSagaStartEvent)
    assert event.correlation_id == saga_id
    assert event.connection_id == str(connection_id)
    uow.commit.assert_awaited()


# ── P2-08: consent expiry ───────────────────────────────────────────


def _make_connection(connection_id, expires_at=None, status: str = "active") -> BankConnection:
    return BankConnection(
        id=connection_id,
        account_id=1,
        user_id=2,
        session_id="sess-1",
        bank_name="Nordea",
        bank_country="DK",
        bank_account_uid="uid-1",
        status=status,
        expires_at=expires_at,
    )


@pytest.mark.asyncio
async def test_complete_connect_persists_valid_until_on_new_connection(
    service: BankingService,
    uow: MagicMock,
    banking_client: AsyncMock,
) -> None:
    valid_until = "2026-10-12T00:00:00+00:00"
    uow.pending_auth.consume.return_value = (1, 2)
    banking_client.create_session.return_value = {
        "session_id": "sess-1",
        "access": {"valid_until": valid_until},
        "aspsp": {"name": "Nordea", "country": "DK"},
        "accounts": [{"uid": "uid-1", "account_id": {"iban": "DK123"}}],
    }
    uow.connections.get_active_by_uid.return_value = None

    created = await service.complete_connect("auth-code", "state-1")

    assert len(created) == 1
    saved_conn = uow.connections.save.await_args.args[0]
    assert saved_conn.expires_at == datetime.fromisoformat(valid_until)


@pytest.mark.asyncio
async def test_complete_connect_refreshes_consent_on_reconnect(
    service: BankingService,
    uow: MagicMock,
    banking_client: AsyncMock,
) -> None:
    connection_id = uuid4()
    existing = _make_connection(connection_id, expires_at=FROZEN_NOW - timedelta(days=1))
    uow.pending_auth.consume.return_value = (1, 2)
    banking_client.create_session.return_value = {
        "session_id": "sess-2",
        "access": {"valid_until": "2026-10-12T00:00:00Z"},
        "aspsp": {"name": "Nordea", "country": "DK"},
        "accounts": [{"uid": "uid-1", "account_id": {"iban": "DK123"}}],
    }
    uow.connections.get_active_by_uid.return_value = existing

    created = await service.complete_connect("auth-code", "state-1")

    assert created[0]["status"] == "reconnected"
    uow.connections.update_consent.assert_awaited_once_with(
        connection_id,
        "sess-2",
        datetime(2026, 10, 12, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_complete_connect_leaves_expiry_null_when_valid_until_missing(
    service: BankingService,
    uow: MagicMock,
    banking_client: AsyncMock,
) -> None:
    uow.pending_auth.consume.return_value = (1, 2)
    banking_client.create_session.return_value = {
        "session_id": "sess-1",
        "aspsp": {"name": "Nordea", "country": "DK"},
        "accounts": [{"uid": "uid-1", "account_id": {"iban": "DK123"}}],
    }
    uow.connections.get_active_by_uid.return_value = None

    created = await service.complete_connect("auth-code", "state-1")

    assert len(created) == 1
    saved_conn = uow.connections.save.await_args.args[0]
    assert saved_conn.expires_at is None


@pytest.mark.asyncio
async def test_start_sync_saga_rejects_expired_consent(
    service: BankingService,
    uow: MagicMock,
) -> None:
    connection_id = uuid4()
    conn = _make_connection(connection_id, expires_at=FROZEN_NOW - timedelta(seconds=1))
    uow.connections.get_by_id.return_value = conn

    with pytest.raises(BankConsentExpired):
        await service.start_sync_saga(connection_id, user_id=2)

    uow.outbox.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_sync_saga_allows_unexpired_consent(
    service: BankingService,
    uow: MagicMock,
) -> None:
    connection_id = uuid4()
    conn = _make_connection(connection_id, expires_at=FROZEN_NOW + timedelta(days=30))
    uow.connections.get_by_id.return_value = conn
    uow.accounts.get_projection.return_value = (2, "Main Account")

    saga_id = await service.start_sync_saga(connection_id, user_id=2)

    assert saga_id
    uow.outbox.add.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_sync_saga_handles_naive_expiry_from_db(
    service: BankingService,
    uow: MagicMock,
) -> None:
    # expires_at comes back naive (UTC wall-clock) from the DB — the
    # domain check must still compare correctly against the aware clock.
    connection_id = uuid4()
    naive_past = (FROZEN_NOW - timedelta(days=1)).replace(tzinfo=None)
    conn = _make_connection(connection_id, expires_at=naive_past)
    uow.connections.get_by_id.return_value = conn

    with pytest.raises(BankConsentExpired):
        await service.start_sync_saga(connection_id, user_id=2)
