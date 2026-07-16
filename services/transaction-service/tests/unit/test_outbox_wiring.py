"""Wiring test: bulk_import → REAL SQLAlchemyUnitOfWork → shared outbox.

The service unit tests mock the UoW, so a signature mismatch between the
application's ``outbox.add_batch(...)`` calls and the adapter actually
wired in production is invisible to them.  That gap shipped once:
wave-B wired ``messaging.OutboxRepository`` in directly, whose
``add_batch(events, aggregate_type, aggregate_id)`` cannot accept the
port's per-entry tuples — every CSV/bulk import crashed with a
TypeError while the mocked suites stayed green.  This test drives the
real UoW on sqlite so the port/adapter/shared-package seam stays covered.

(sqlite note: the partial unique index from migration 012 is declared
with ``postgresql_where`` and therefore materializes as a plain unique
index here — irrelevant for this test, which imports distinct rows.)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.dto import BulkCreateTransactionDTO, BulkCreateTransactionItemDTO
from app.application.service import TransactionService
from app.database import Base
from app.models import OutboxEventModel, TransactionModel
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
async def test_bulk_import_writes_rows_and_per_entry_outbox_events(session) -> None:  # type: ignore[no-untyped-def]
    service = TransactionService(uow=SQLAlchemyUnitOfWork(session), categorization_client=None)
    dto = BulkCreateTransactionDTO(
        items=[
            BulkCreateTransactionItemDTO(
                account_id=1,
                account_name="Konto",
                amount=Decimal("49.99"),
                transaction_type="expense",
                date=date(2026, 3, 1),
                description="Netto",
                external_id="EB-1",
                currency="DKK",
            ),
            BulkCreateTransactionItemDTO(
                account_id=1,
                account_name="Konto",
                amount=Decimal("15000.00"),
                transaction_type="income",
                date=date(2026, 3, 1),
                description="Løn",
                external_id="EB-2",
                currency="DKK",
            ),
        ],
    )

    result = await service.bulk_import(user_id=10, dto=dto)

    assert result.imported == 2
    tx_rows = (await session.execute(select(TransactionModel))).scalars().all()
    assert {t.external_id for t in tx_rows} == {"EB-1", "EB-2"}

    outbox_rows = (await session.execute(select(OutboxEventModel))).scalars().all()
    assert len(outbox_rows) == 2
    assert all(r.event_type == "transaction.created" for r in outbox_rows)
    # Per-entry aggregates: each event must reference ITS transaction row.
    assert {r.aggregate_id for r in outbox_rows} == {str(t.id) for t in tx_rows}
