from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.database import Base
from app.models import OutboxEventModel
from app.workers import outbox_publisher as worker_module
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.mark.asyncio()
async def test_worker_marks_failed_and_increments_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
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
                    id="evt-retry-1",
                    aggregate_type="goal",
                    aggregate_id="200",
                    event_type="goal.created",
                    payload_json='{"goal_id":200,"user_id":99}',
                    status="pending",
                    attempts=0,
                )
            )
            await session.commit()

        monkeypatch.setattr(worker_module, "async_session_factory", session_factory)

        # publisher that raises to simulate failure
        publisher = AsyncMock()
        publisher.publish_raw.side_effect = RuntimeError("connection error")

        worker = worker_module.OutboxPublisherWorker(publisher=publisher, batch_size=10)

        processed = await worker._process_batch()
        assert processed == 1

        async with session_factory() as session:
            result = await session.execute(select(OutboxEventModel).where(OutboxEventModel.id == "evt-retry-1"))
            row = result.scalar_one()
            assert row.status == "failed"
            assert row.attempts == 1
            assert row.next_attempt_at is not None
    finally:
        await engine.dispose()
