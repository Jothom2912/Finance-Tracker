from __future__ import annotations

from unittest.mock import AsyncMock

from app.application.dto import GoalResponse
from app.auth import get_current_user_id
from app.domain.entities import GoalStatus
from app.domain.exceptions import NotAccountOwner
from app.main import app
from fastapi.testclient import TestClient


class DummyService:
    def __init__(self) -> None:
        self.get_goal = AsyncMock()
        self.list_goals = AsyncMock()
        self.create_goal = AsyncMock()
        self.update_goal = AsyncMock()
        self.delete_goal = AsyncMock()


def _goal_response(**overrides) -> GoalResponse:
    defaults = dict(
        idGoal=10,
        name="Vacation",
        target_amount=5000,
        current_amount=1000,
        target_date=None,
        status=GoalStatus.ACTIVE,
        effective_status=GoalStatus.ACTIVE,
        progress_percent=20.0,
        Account_idAccount=1,
    )
    defaults.update(overrides)
    return GoalResponse(**defaults)


def client_with_service(service: DummyService) -> TestClient:
    from app.dependencies import get_goal_service

    app.dependency_overrides[get_goal_service] = lambda: service
    app.dependency_overrides[get_current_user_id] = lambda: 1
    return TestClient(app)


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "goal-service"}


def test_goal_routes_require_authentication() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/api/v1/goals/123")

    assert response.status_code == 401


def test_get_goal_returns_404_when_missing() -> None:
    service = DummyService()
    service.get_goal.return_value = None
    client = client_with_service(service)

    response = client.get("/api/v1/goals/123")

    assert response.status_code == 404
    assert response.json()["detail"] == "Goal not found"
    app.dependency_overrides.clear()


def test_get_goal_passes_user_id() -> None:
    service = DummyService()
    service.get_goal.return_value = _goal_response()
    client = client_with_service(service)

    response = client.get("/api/v1/goals/10")

    assert response.status_code == 200
    service.get_goal.assert_awaited_once_with(10, 1)
    app.dependency_overrides.clear()


def test_create_goal_returns_201() -> None:
    service = DummyService()
    service.create_goal.return_value = _goal_response()
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
    assert response.json()["effective_status"] == "active"
    assert response.json()["progress_percent"] == 20.0
    app.dependency_overrides.clear()


def test_update_goal_and_delete_goal_routes() -> None:
    service = DummyService()
    service.update_goal.return_value = _goal_response(
        name="Vacation 2",
        target_amount=7000,
        current_amount=1500,
        status=GoalStatus.PAUSED,
        effective_status=GoalStatus.PAUSED,
        progress_percent=21.43,
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


def test_list_goals_returns_200_with_account_header() -> None:
    service = DummyService()
    service.list_goals.return_value = [_goal_response(), _goal_response(idGoal=11, name="Car")]
    client = client_with_service(service)

    response = client.get("/api/v1/goals", headers={"X-Account-ID": "1"})

    assert response.status_code == 200
    assert len(response.json()) == 2
    service.list_goals.assert_awaited_once_with(1, 1)
    app.dependency_overrides.clear()


def test_list_goals_returns_422_without_account_header() -> None:
    service = DummyService()
    client = client_with_service(service)

    response = client.get("/api/v1/goals")

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_list_goals_returns_400_with_invalid_account_header() -> None:
    service = DummyService()
    client = client_with_service(service)

    response = client.get("/api/v1/goals", headers={"X-Account-ID": "abc"})

    assert response.status_code == 400
    app.dependency_overrides.clear()


def test_list_goals_returns_403_for_non_owner() -> None:
    service = DummyService()
    service.list_goals.side_effect = NotAccountOwner()
    client = client_with_service(service)

    response = client.get("/api/v1/goals", headers={"X-Account-ID": "1"})

    assert response.status_code == 403
    app.dependency_overrides.clear()
