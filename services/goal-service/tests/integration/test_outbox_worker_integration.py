from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import OutboxEventModel
from app.workers import outbox_publisher as worker_module


@pytest.mark.asyncio()
async def test_worker_marks_pending_event_as_published(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            session.add(
                OutboxEventModel(
                    id="evt-1",
                    aggregate_type="goal",
                    aggregate_id="123",
                    event_type="goal.created",
                    payload_json='{"goal_id":123,"user_id":42}',
                    status="pending",
                    attempts=0,
                )
            )
            await session.commit()

        monkeypatch.setattr(worker_module, "async_session_factory", session_factory)

        publisher = SimpleNamespace(publish_raw=AsyncMock())
        worker = worker_module.OutboxPublisherWorker(publisher=publisher, batch_size=20)

        processed = await worker._process_batch()
        assert processed == 1
        publisher.publish_raw.assert_awaited_once()

        async with session_factory() as session:
            result = await session.execute(
                select(OutboxEventModel).where(OutboxEventModel.id == "evt-1")
            )
            row = result.scalar_one()
            assert row.status == "published"
            assert row.published_at is not None
    finally:
        await engine.dispose()
