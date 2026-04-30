from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.application.dto import Goal as GoalDTO
from app.main import app


class DummyService:
    def __init__(self) -> None:
        self.get_goal = AsyncMock()
        self.create_goal = AsyncMock()
        self.update_goal = AsyncMock()
        self.delete_goal = AsyncMock()


def client_with_service(service: DummyService) -> TestClient:
    from app.dependencies import get_goal_service

    app.dependency_overrides[get_goal_service] = lambda: service
    return TestClient(app)


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "goal-service"}


def test_get_goal_returns_404_when_missing() -> None:
    service = DummyService()
    service.get_goal.return_value = None
    client = client_with_service(service)

    response = client.get("/api/v1/goals/123")

    assert response.status_code == 404
    assert response.json()["detail"] == "Goal not found"
    app.dependency_overrides.clear()


def test_create_goal_returns_201() -> None:
    service = DummyService()
    service.create_goal.return_value = GoalDTO(
        idGoal=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status="active",
        Account_idAccount=1,
    )
    client = client_with_service(service)

    response = client.post(
        "/api/v1/goals",
        json={
            "name": "Vacation",
            "target_amount": 5000,
            "current_amount": 1000,
            "target_date": None,
            "status": "active",
            "Account_idAccount": 1,
        },
    )

    assert response.status_code == 201
    assert response.json()["idGoal"] == 10
    app.dependency_overrides.clear()


def test_update_goal_and_delete_goal_routes() -> None:
    service = DummyService()
    service.update_goal.return_value = GoalDTO(
        idGoal=10,
        name="Vacation 2",
        target_amount=7000,
        current_amount=1500,
        target_date=None,
        status="paused",
        Account_idAccount=1,
    )
    service.delete_goal.return_value = True
    client = client_with_service(service)

    update_response = client.put(
        "/api/v1/goals/10",
        json={
            "name": "Vacation 2",
            "target_amount": 7000,
            "current_amount": 1500,
            "target_date": None,
            "status": "paused",
        },
    )
    delete_response = client.delete("/api/v1/goals/10")

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Vacation 2"
    assert delete_response.status_code == 204
    app.dependency_overrides.clear()
