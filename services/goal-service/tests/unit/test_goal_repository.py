from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.adapters.outbound.postgres_goal_repository import AsyncPostgresGoalRepository
from app.database import Base
from app.domain.entities import Goal


@pytest.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio()
async def test_create_get_all_and_get_by_id(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        repo = AsyncPostgresGoalRepository(session)

        first = await repo.create(
            Goal(
                id=None,
                name="Vacation",
                target_amount=5000,
                current_amount=500,
                target_date=date(2026, 12, 31),
                status="active",
                account_id=1,
            )
        )
        second = await repo.create(
            Goal(
                id=None,
                name="Emergency",
                target_amount=10000,
                current_amount=2000,
                target_date=None,
                status="active",
                account_id=1,
            )
        )
        await session.commit()

        fetched = await repo.get_by_id(second.id)
        all_goals = await repo.get_all(account_id=1)

        assert fetched is not None
        assert fetched.name == "Emergency"
        assert [goal.id for goal in all_goals] == [second.id, first.id]


@pytest.mark.asyncio()
async def test_update_and_delete(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        repo = AsyncPostgresGoalRepository(session)

        created = await repo.create(
            Goal(
                id=None,
                name="Vacation",
                target_amount=5000,
                current_amount=500,
                target_date=None,
                status="active",
                account_id=1,
            )
        )
        await session.commit()

        updated = await repo.update(
            Goal(
                id=created.id,
                name="Vacation 2",
                target_amount=7000,
                current_amount=1500,
                target_date=None,
                status="paused",
                account_id=1,
            )
        )
        deleted = await repo.delete(created.id)
        await session.commit()

        assert updated.name == "Vacation 2"
        assert updated.current_amount == 1500
        assert deleted is True
        assert await repo.get_by_id(created.id) is None
