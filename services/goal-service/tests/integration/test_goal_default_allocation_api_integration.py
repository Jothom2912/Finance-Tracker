from __future__ import annotations

from decimal import Decimal

import pytest
from app.adapters.outbound.postgres_goal_allocation_repository import (
    PostgresGoalAllocationRepository,
    PostgresUnallocatedBudgetSurplusRepository,
)
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.service import GoalService
from app.auth import get_current_user_id
from app.database import Base
from app.dependencies import get_goal_service
from app.main import app
from app.models import GoalModel
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

ACCOUNT_ID = 42


class _AccountPortStub:
    async def get_owner_user_id(self, account_id: int) -> int:
        return 1

    async def exists(self, account_id: int) -> bool:
        return True


@pytest.fixture()
async def api_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = session_factory()
    service = GoalService(uow=SQLAlchemyUnitOfWork(session), account_port=_AccountPortStub())

    async def override_goal_service():
        yield service

    app.dependency_overrides[get_goal_service] = override_goal_service
    app.dependency_overrides[get_current_user_id] = lambda: 1

    try:
        with TestClient(app) as client:
            yield client, session_factory, session
    finally:
        app.dependency_overrides.clear()
        await session.close()
        await engine.dispose()


def _create_goal(client: TestClient, name: str) -> int:
    response = client.post(
        "/api/v1/goals",
        json={
            "name": name,
            "target_amount": 5000,
            "current_amount": 0,
            "target_date": None,
            "status": "active",
            "Account_idAccount": ACCOUNT_ID,
        },
    )
    assert response.status_code == 201
    return response.json()["idGoal"]


@pytest.mark.asyncio()
async def test_set_default_switches_between_goals_and_survives_unique_index(api_client) -> None:
    client, session_factory, _session = api_client
    first = _create_goal(client, "Ferie")
    second = _create_goal(client, "Nodopsparing")

    set_first = client.put(f"/api/v1/goals/{first}/default")
    assert set_first.status_code == 200
    assert set_first.json()["is_default_savings_goal"] is True

    # Skift til det andet mål — clear-then-set må ikke vælte på det partielle unique index.
    set_second = client.put(f"/api/v1/goals/{second}/default")
    assert set_second.status_code == 200
    assert set_second.json()["is_default_savings_goal"] is True

    listed = client.get("/api/v1/goals", headers={"X-Account-ID": str(ACCOUNT_ID)}).json()
    defaults = {goal["idGoal"]: goal["is_default_savings_goal"] for goal in listed}
    assert defaults == {first: False, second: True}

    async with session_factory() as verify_session:
        result = await verify_session.execute(select(GoalModel).where(GoalModel.is_default_savings_goal.is_(True)))
        assert [model.idGoal for model in result.scalars().all()] == [second]


@pytest.mark.asyncio()
async def test_clear_default_goal(api_client) -> None:
    client, _session_factory, _session = api_client
    goal_id = _create_goal(client, "Ferie")
    client.put(f"/api/v1/goals/{goal_id}/default")

    cleared = client.delete(f"/api/v1/goals/{goal_id}/default")

    assert cleared.status_code == 200
    assert cleared.json()["is_default_savings_goal"] is False


@pytest.mark.asyncio()
async def test_set_default_on_missing_goal_returns_404(api_client) -> None:
    client, _session_factory, _session = api_client
    assert client.put("/api/v1/goals/9999/default").status_code == 404


@pytest.mark.asyncio()
async def test_allocation_history_returns_seeded_rows_newest_first(api_client) -> None:
    client, _session_factory, session = api_client
    goal_id = _create_goal(client, "Ferie")

    repo = PostgresGoalAllocationRepository(session)
    await repo.add_allocation(
        source_key=f"budget.month_closed:{ACCOUNT_ID}:2026:5",
        goal_id=goal_id,
        account_id=ACCOUNT_ID,
        amount=Decimal("100.00"),
        correlation_id=None,
    )
    await repo.add_allocation(
        source_key=f"budget.month_closed:{ACCOUNT_ID}:2026:6",
        goal_id=goal_id,
        account_id=ACCOUNT_ID,
        amount=Decimal("250.00"),
        correlation_id=None,
    )
    await session.commit()

    response = client.get(f"/api/v1/goals/{goal_id}/allocation-history")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {entry["source_key"] for entry in body} == {
        f"budget.month_closed:{ACCOUNT_ID}:2026:5",
        f"budget.month_closed:{ACCOUNT_ID}:2026:6",
    }
    assert all(entry["amount"] > 0 and entry["applied_at"] for entry in body)


@pytest.mark.asyncio()
async def test_allocation_history_on_missing_goal_returns_404(api_client) -> None:
    client, _session_factory, _session = api_client
    assert client.get("/api/v1/goals/9999/allocation-history").status_code == 404


@pytest.mark.asyncio()
async def test_unallocated_surplus_route_not_shadowed_and_sums(api_client) -> None:
    client, _session_factory, session = api_client

    repo = PostgresUnallocatedBudgetSurplusRepository(session)
    await repo.add_unallocated(
        source_key=f"budget.month_closed:{ACCOUNT_ID}:2026:5",
        account_id=ACCOUNT_ID,
        amount=Decimal("100.50"),
        reason="no_default_goal",
        correlation_id=None,
    )
    await repo.add_unallocated(
        source_key=f"budget.month_closed:{ACCOUNT_ID}:2026:6",
        account_id=ACCOUNT_ID,
        amount=Decimal("49.50"),
        reason="goal_already_complete",
        correlation_id=None,
    )
    await session.commit()

    # Rammer den statiske rute — ikke /{goal_id} (som ville give 422 på int-parse).
    response = client.get(
        "/api/v1/goals/unallocated-surplus",
        headers={"X-Account-ID": str(ACCOUNT_ID)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 150.0
    assert {entry["reason"] for entry in body["entries"]} == {"no_default_goal", "goal_already_complete"}


@pytest.mark.asyncio()
async def test_unallocated_surplus_empty_account_returns_zero_total(api_client) -> None:
    client, _session_factory, _session = api_client

    response = client.get(
        "/api/v1/goals/unallocated-surplus",
        headers={"X-Account-ID": str(ACCOUNT_ID)},
    )

    assert response.status_code == 200
    assert response.json() == {"total": 0.0, "entries": []}
