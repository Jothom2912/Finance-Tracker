from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.adapters.outbound.postgres_goal_repository import AsyncPostgresGoalRepository
from app.database import Base
from app.domain.entities import Goal
from app.models import GoalAllocationHistoryModel, GoalModel
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


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


# --- Soft-delete (P3-16) ---


async def _create_goal(repo: AsyncPostgresGoalRepository, *, account_id: int = 1, name: str = "Vacation") -> Goal:
    return await repo.create(
        Goal(
            id=None,
            name=name,
            target_amount=5000,
            current_amount=500,
            target_date=None,
            status="active",
            account_id=account_id,
        )
    )


async def _raw_goal_row(session: AsyncSession, goal_id: int) -> tuple:
    # Kolonne-select udenom ORM-identity-map: viser rækkens faktiske tilstand
    # uden repo'ets deleted_at-filter.
    result = await session.execute(
        select(GoalModel.deleted_at, GoalModel.is_default_savings_goal).where(GoalModel.idGoal == goal_id)
    )
    return result.one()


@pytest.mark.asyncio()
async def test_delete_is_soft_preserves_row_and_clears_default_flag(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = AsyncPostgresGoalRepository(session)
        created = await _create_goal(repo)
        await repo.set_default_savings_goal(created.id, account_id=1)
        await session.commit()

        deleted = await repo.delete(created.id)
        await session.commit()

        assert deleted is True
        deleted_at, is_default = await _raw_goal_row(session, created.id)
        assert deleted_at is not None
        assert not is_default
        assert await repo.get_by_id(created.id) is None


@pytest.mark.asyncio()
async def test_delete_twice_returns_false(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        repo = AsyncPostgresGoalRepository(session)
        created = await _create_goal(repo)
        await session.commit()

        assert await repo.delete(created.id) is True
        assert await repo.delete(created.id) is False


@pytest.mark.asyncio()
async def test_deleted_goal_excluded_from_get_all(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        repo = AsyncPostgresGoalRepository(session)
        kept = await _create_goal(repo, name="Kept")
        removed = await _create_goal(repo, name="Removed")
        await session.commit()

        await repo.delete(removed.id)
        await session.commit()

        assert [goal.id for goal in await repo.get_all(account_id=1)] == [kept.id]


@pytest.mark.asyncio()
async def test_update_deleted_goal_raises(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        repo = AsyncPostgresGoalRepository(session)
        created = await _create_goal(repo)
        await session.commit()
        await repo.delete(created.id)

        with pytest.raises(ValueError, match="not found"):
            await repo.update(
                Goal(
                    id=created.id,
                    name="Zombie",
                    target_amount=1,
                    current_amount=0,
                    target_date=None,
                    status="active",
                    account_id=1,
                )
            )


@pytest.mark.asyncio()
async def test_set_default_savings_goal_skips_deleted_goal(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = AsyncPostgresGoalRepository(session)
        created = await _create_goal(repo)
        await session.commit()
        await repo.delete(created.id)

        await repo.set_default_savings_goal(created.id, account_id=1)
        await session.commit()

        _, is_default = await _raw_goal_row(session, created.id)
        assert not is_default


@pytest.mark.asyncio()
async def test_delete_goal_with_allocation_history_succeeds_under_fk_enforcement() -> None:
    # Regressionstest for finding F-2026-07-17-01: hard-delete på et mål med
    # goal_allocation_history-rækker gav FK-fejl → 500. sqlite håndhæver kun
    # FK'er med pragma'et slået til, så det aktiveres eksplicit her — uden det
    # ville testen have været grøn selv med den gamle hard-delete.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with factory() as session:
            repo = AsyncPostgresGoalRepository(session)
            created = await _create_goal(repo)
            session.add(
                GoalAllocationHistoryModel(
                    id=str(uuid4()),
                    source_key="budget.month_closed:1:2026:6",
                    goal_id=created.id,
                    account_id=1,
                    amount=Decimal("150.00"),
                    correlation_id=None,
                )
            )
            await session.commit()

            deleted = await repo.delete(created.id)
            await session.commit()

            assert deleted is True
            history = await session.execute(
                select(GoalAllocationHistoryModel).where(GoalAllocationHistoryModel.goal_id == created.id)
            )
            assert len(history.scalars().all()) == 1
    finally:
        await engine.dispose()
