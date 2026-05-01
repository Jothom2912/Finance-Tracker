from __future__ import annotations

import pytest
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.service import GoalService
from app.database import Base
from app.main import app
from app.models import GoalModel
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


class _AccountPortStub:
    async def exists(self, _user_id: int) -> bool:
        return True


@pytest.mark.asyncio()
async def test_goal_api_round_trip_persists_through_service_and_repository() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session = session_factory()
        service = GoalService(uow=SQLAlchemyUnitOfWork(session), account_port=_AccountPortStub())

        async def override_goal_service():
            yield service

        from app.dependencies import get_goal_service

        app.dependency_overrides[get_goal_service] = override_goal_service

        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/goals",
                json={
                    "name": "Vacation",
                    "target_amount": 5000,
                    "current_amount": 1000,
                    "target_date": None,
                    "status": "active",
                    "Account_idAccount": 42,
                },
            )
            assert create_response.status_code == 201
            goal_id = create_response.json()["idGoal"]

            get_response = client.get(f"/api/v1/goals/{goal_id}")
            assert get_response.status_code == 200
            assert get_response.json()["name"] == "Vacation"

            update_response = client.put(
                f"/api/v1/goals/{goal_id}",
                json={
                    "name": "Vacation 2",
                    "target_amount": 6000,
                    "current_amount": 1500,
                    "target_date": None,
                    "status": "paused",
                },
            )
            assert update_response.status_code == 200
            assert update_response.json()["name"] == "Vacation 2"

            delete_response = client.delete(f"/api/v1/goals/{goal_id}")
            assert delete_response.status_code == 204

            missing_response = client.get(f"/api/v1/goals/{goal_id}")
            assert missing_response.status_code == 404

        async with session_factory() as verify_session:
            result = await verify_session.execute(select(GoalModel).where(GoalModel.idGoal == goal_id))
            assert result.scalar_one_or_none() is None
    finally:
        app.dependency_overrides.clear()
        await session.close()
        await engine.dispose()
