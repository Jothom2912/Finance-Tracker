from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.dto import GoalBase, GoalCreate
from app.application.service import GoalService
from app.database import Base
from app.models import OutboxEventModel


class _AccountPortStub:
    async def exists(self, _user_id: int) -> bool:
        return True


def _create_test_engine():
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.mark.asyncio()
async def test_create_goal_persists_outbox_event() -> None:
    engine = _create_test_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            service = GoalService(
                uow=SQLAlchemyUnitOfWork(session),
                account_port=_AccountPortStub(),
            )

            created = await service.create_goal(
                GoalCreate(
                    name="Emergency fund",
                    target_amount=15000,
                    current_amount=1500,
                    target_date=None,
                    status="active",
                    Account_idAccount=42,
                )
            )

            assert created.idGoal is not None

            result = await session.execute(select(OutboxEventModel))
            outbox_rows = result.scalars().all()
            assert len(outbox_rows) == 1

            row = outbox_rows[0]
            assert row.aggregate_type == "goal"
            assert row.aggregate_id == str(created.idGoal)
            assert row.event_type == "goal.created"
            assert row.status == "pending"

            payload = json.loads(row.payload_json)
            assert payload["goal_id"] == created.idGoal
            assert payload["user_id"] == 42
    finally:
        await engine.dispose()


@pytest.mark.asyncio()
async def test_update_goal_persists_outbox_event() -> None:
    engine = _create_test_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            service = GoalService(
                uow=SQLAlchemyUnitOfWork(session),
                account_port=_AccountPortStub(),
            )

            created = await service.create_goal(
                GoalCreate(
                    name="Emergency fund",
                    target_amount=15000,
                    current_amount=1500,
                    target_date=None,
                    status="active",
                    Account_idAccount=42,
                )
            )

            updated = await service.update_goal(
                created.idGoal,
                GoalBase(
                    name="Emergency fund updated",
                    target_amount=18000,
                    current_amount=2000,
                    target_date=None,
                    status="active",
                ),
            )

            assert updated is not None

            result = await session.execute(select(OutboxEventModel).order_by(OutboxEventModel.created_at))
            outbox_rows = result.scalars().all()
            assert len(outbox_rows) == 2
            assert outbox_rows[0].event_type == "goal.created"
            assert outbox_rows[1].event_type == "goal.updated"
            assert outbox_rows[1].aggregate_id == str(created.idGoal)

            payload = json.loads(outbox_rows[1].payload_json)
            assert payload["goal_id"] == created.idGoal
            assert payload["name"] == "Emergency fund updated"
    finally:
        await engine.dispose()


@pytest.mark.asyncio()
async def test_delete_goal_persists_outbox_event() -> None:
    engine = _create_test_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            service = GoalService(
                uow=SQLAlchemyUnitOfWork(session),
                account_port=_AccountPortStub(),
            )

            created = await service.create_goal(
                GoalCreate(
                    name="Emergency fund",
                    target_amount=15000,
                    current_amount=1500,
                    target_date=None,
                    status="active",
                    Account_idAccount=42,
                )
            )

            deleted = await service.delete_goal(created.idGoal)
            assert deleted is True

            result = await session.execute(select(OutboxEventModel).order_by(OutboxEventModel.created_at))
            outbox_rows = result.scalars().all()
            assert len(outbox_rows) == 2
            assert outbox_rows[0].event_type == "goal.created"
            assert outbox_rows[1].event_type == "goal.deleted"
            assert outbox_rows[1].aggregate_id == str(created.idGoal)

            payload = json.loads(outbox_rows[1].payload_json)
            assert payload["goal_id"] == created.idGoal
            assert payload["user_id"] == 42
    finally:
        await engine.dispose()
