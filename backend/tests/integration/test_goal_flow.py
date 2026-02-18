"""Integration tests for goal flows (HTTP -> Service -> Repository -> DB)."""

import pytest
from decimal import Decimal

from .conftest import Factory


class TestGoalCreation:
    """Tests for creating goals through the API."""

    def test_create_goal_returns_201(
        self, test_client, test_db, mock_repositories, account_headers, seed_account
    ):
        # Act - omit target_date (optional) to avoid SQLite string-to-date issue
        response = test_client.post(
            "/goals/",
            json={
                "name": "Sommerferie",
                "target_amount": 15000.0,
            },
            headers=account_headers,
        )

        # Assert
        assert response.status_code == 201, response.json()
        data = response.json()
        assert data["name"] == "Sommerferie"
        assert float(data["target_amount"]) == 15000.0

    def test_create_goal_without_account_returns_400(
        self, test_client, test_db, mock_repositories
    ):
        # Act - no account header, no auth
        response = test_client.post(
            "/goals/",
            json={
                "name": "No Account Goal",
                "target_amount": 5000.0,
            },
        )

        # Assert
        assert response.status_code == 400

    def test_create_goal_with_initial_progress(
        self, test_client, test_db, mock_repositories, account_headers, seed_account
    ):
        # Act - omit target_date (optional) to avoid SQLite string-to-date issue
        response = test_client.post(
            "/goals/",
            json={
                "name": "Ny bil",
                "target_amount": 200000.0,
                "current_amount": 50000.0,
            },
            headers=account_headers,
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert float(data["current_amount"]) == 50000.0


class TestGoalRetrieval:
    """Tests for fetching goals."""

    def test_get_goals_returns_list(
        self, test_client, test_db, mock_repositories, account_headers, seed_account
    ):
        # Arrange - create goals directly in DB
        Factory.goal(test_db, seed_account.idAccount, name="Ferie")
        Factory.goal(test_db, seed_account.idAccount, name="Nødopsparing")
        test_db.flush()
        test_db.expire_all()

        # Act
        response = test_client.get(
            "/goals/",
            headers=account_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        names = [g["name"] for g in data]
        assert "Ferie" in names
        assert "Nødopsparing" in names

    def test_get_goal_by_id_returns_200(
        self, test_client, test_db, mock_repositories, seed_account
    ):
        # Arrange
        goal = Factory.goal(test_db, seed_account.idAccount, name="Specifikt mål")
        test_db.flush()
        test_db.expire_all()

        # Act
        response = test_client.get(f"/goals/{goal.idGoal}")

        # Assert
        assert response.status_code == 200
        assert response.json()["name"] == "Specifikt mål"

    def test_get_nonexistent_goal_returns_404(
        self, test_client, test_db, mock_repositories
    ):
        # Act
        response = test_client.get("/goals/99999")

        # Assert
        assert response.status_code == 404


class TestGoalLifecycle:
    """Tests for updating and deleting goals."""

    def test_update_goal_progress(
        self, test_client, test_db, mock_repositories, seed_account
    ):
        # Arrange - create goal without target_date to avoid SQLite compat issue
        goal = Factory.goal(
            test_db,
            seed_account.idAccount,
            name="Progress Test",
            target_amount=Decimal("10000"),
            current_amount=Decimal("0"),
            target_date=None,
        )
        test_db.flush()
        test_db.expire_all()

        # Act - update current_amount (no target_date to avoid SQLite string-to-date)
        response = test_client.put(
            f"/goals/{goal.idGoal}",
            json={
                "name": "Progress Test",
                "target_amount": 10000.0,
                "current_amount": 2500.0,
                "status": "active",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert float(data["current_amount"]) == 2500.0

    def test_delete_goal_returns_204(
        self, test_client, test_db, mock_repositories, seed_account
    ):
        # Arrange
        goal = Factory.goal(test_db, seed_account.idAccount)
        test_db.flush()
        test_db.expire_all()

        # Act
        response = test_client.delete(f"/goals/{goal.idGoal}")

        # Assert
        assert response.status_code == 204

    def test_delete_nonexistent_goal_returns_404(
        self, test_client, test_db, mock_repositories
    ):
        # Act
        response = test_client.delete("/goals/99999")

        # Assert
        assert response.status_code == 404
