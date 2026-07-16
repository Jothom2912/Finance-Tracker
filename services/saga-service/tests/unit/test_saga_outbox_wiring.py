"""Wiring test: orchestrator → REAL SQLAlchemyUnitOfWork → shared outbox.

The orchestrator unit tests run against in-memory fakes of the ports, so
they can never catch a signature mismatch between the orchestrator's
``outbox.add(...)`` calls and the adapter actually wired in production.
That exact gap shipped once: wave-B wired ``messaging.OutboxRepository``
in directly and every ``start_saga`` crashed with
``TypeError: add() got an unexpected keyword argument 'event_type'``
while 49 green unit tests looked on.  This test drives the real UoW
against sqlite so the port/adapter/shared-package seam is exercised.
"""

from __future__ import annotations

import json

import pytest
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.orchestrator import SagaOrchestrator, SagaRegistry
from app.application.sagas.bank_sync_saga import BankSyncSagaDefinition
from app.database import Base
from app.models import OutboxEventModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session():  # type: ignore[no-untyped-def]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_start_saga_writes_command_to_real_outbox(session) -> None:  # type: ignore[no-untyped-def]
    registry = SagaRegistry()
    registry.register(BankSyncSagaDefinition())
    uow = SQLAlchemyUnitOfWork(session)
    orchestrator = SagaOrchestrator(uow, registry)

    saga = await orchestrator.start_saga(
        "bank_sync",
        {
            "connection_id": "conn-1",
            "user_id": 10,
            "account_id": 100,
            "account_name": "Main",
            "bank_account_uid": "uid-1",
        },
        correlation_id="corr-1",
    )

    rows = (await session.execute(select(OutboxEventModel))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == "saga.cmd.bank_fetch_transactions"
    assert row.aggregate_type == "saga"
    assert row.aggregate_id == saga.id
    assert row.correlation_id == "corr-1"
    payload = json.loads(row.payload_json)
    assert payload["saga_id"] == saga.id
    assert payload["bank_account_uid"] == "uid-1"
