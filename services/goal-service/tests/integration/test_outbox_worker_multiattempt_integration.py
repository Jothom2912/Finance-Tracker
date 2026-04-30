from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import OutboxEventModel
from app.workers import outbox_publisher as worker_module


@pytest.mark.asyncio()
async def test_worker_retries_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
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
                    id="evt-multi-1",
                    aggregate_type="goal",
                    aggregate_id="300",
                    event_type="goal.created",
                    payload_json='{"goal_id":300,"user_id":123}',
                    status="pending",
                    attempts=0,
                )
            )
            await session.commit()

        monkeypatch.setattr(worker_module, "async_session_factory", session_factory)

        # publisher: fail twice, then succeed
        publisher = AsyncMock()
        publisher.publish_raw.side_effect = [RuntimeError("err1"), RuntimeError("err2"), None]

        worker = worker_module.OutboxPublisherWorker(publisher=publisher, batch_size=10)

        # Run three processing cycles; after failures, force next_attempt_at into the past to allow immediate retry
        for i in range(3):
            processed = await worker._process_batch()
            assert processed == 1

            if i < 2:
                # set next_attempt_at to the past so the worker will pick it up again
                async with session_factory() as s:
                    await s.execute(
                        update(OutboxEventModel)
                        .where(OutboxEventModel.id == "evt-multi-1")
                        .values(next_attempt_at=(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=10)))
                    )
                    await s.commit()

        # final check: event should be published
        async with session_factory() as session:
            result = await session.execute(select(OutboxEventModel).where(OutboxEventModel.id == "evt-multi-1"))
            row = result.scalar_one()
            assert row.status == "published"
            assert row.attempts == 2
    finally:
        await engine.dispose()
