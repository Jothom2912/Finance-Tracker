from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.service import BankingService
from app.domain.entities import BankConnection
from app.domain.exceptions import BankAccountNotOwned
from contracts.events.bank import BankConnectionCreatedEvent
from contracts.events.saga import BankSyncSagaStartEvent


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
def banking_client() -> MagicMock:
    client = MagicMock()
    client.start_authorization.return_value = {"url": "https://bank.test/auth", "state": "state-1"}
    return client


@pytest.fixture
def service(
    uow: MagicMock,
    account_port: AsyncMock,
    banking_client: MagicMock,
) -> BankingService:
    return BankingService(
        uow=uow,
        account_port=account_port,
        banking_client=banking_client,
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
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_complete_connect_emits_outbox_event(
    service: BankingService,
    uow: MagicMock,
    banking_client: MagicMock,
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
