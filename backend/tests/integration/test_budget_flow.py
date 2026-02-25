"""Integration tests for budget flows (HTTP -> Service -> Repository -> DB)."""

import pytest
from decimal import Decimal
from datetime import date

from .conftest import Factory


class TestBudgetCreation:
    """Tests for budget creation through the API."""

    def test_create_budget_returns_201(
        self,
        test_client,
        test_db,
        mock_repositories,
        seed_account,
        seed_categories,
        account_headers,
    ):
        # Arrange - category "Mad" is seed_categories[0]
        category = seed_categories[0]

        # Act
        response = test_client.post(
            "/api/v1/budgets/",
            json={
                "amount": 5000.0,
                "category_id": category.idCategory,
                "month": "6",
                "year": "2025",
            },
            headers=account_headers,
        )

        # Assert
        assert response.status_code == 201, response.json()
        data = response.json()
        assert float(data["amount"]) == 5000.0

    def test_create_budget_without_account_returns_400(
        self, test_client, test_db, mock_repositories, seed_categories
    ):
        # Arrange - no X-Account-ID header and no Authorization header
        category = seed_categories[0]

        # Act
        response = test_client.post(
            "/api/v1/budgets/",
            json={
                "amount": 3000.0,
                "category_id": category.idCategory,
                "month": "1",
                "year": "2025",
            },
        )

        # Assert
        assert response.status_code == 400

    def test_create_budget_with_invalid_category_returns_400(
        self,
        test_client,
        test_db,
        mock_repositories,
        seed_account,
        account_headers,
    ):
        # Arrange - category 9999 does not exist

        # Act
        response = test_client.post(
            "/api/v1/budgets/",
            json={
                "amount": 5000.0,
                "category_id": 9999,
                "month": "6",
                "year": "2025",
            },
            headers=account_headers,
        )

        # Assert
        assert response.status_code == 400


class TestBudgetRetrieval:
    """Tests for fetching budgets."""

    def test_get_budgets_returns_list(
        self,
        test_client,
        test_db,
        mock_repositories,
        seed_account,
        seed_categories,
        account_headers,
    ):
        # Arrange - create a budget directly in DB
        Factory.budget(
            test_db,
            seed_account.idAccount,
            seed_categories[0].idCategory,
            Decimal("5000"),
        )
        test_db.flush()
        test_db.expire_all()

        # Act
        response = test_client.get(
            "/api/v1/budgets/",
            headers=account_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_budget_by_id_returns_200(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories
    ):
        # Arrange
        budget = Factory.budget(
            test_db,
            seed_account.idAccount,
            seed_categories[0].idCategory,
            Decimal("3000"),
        )
        test_db.flush()
        test_db.expire_all()

        # Act
        response = test_client.get(f"/api/v1/budgets/{budget.idBudget}")

        # Assert
        assert response.status_code == 200
        assert float(response.json()["amount"]) == 3000.0

    def test_get_nonexistent_budget_returns_404(
        self, test_client, test_db, mock_repositories
    ):
        # Act
        response = test_client.get("/api/v1/budgets/99999")

        # Assert
        assert response.status_code == 404


class TestBudgetLifecycle:
    """Tests for updating and deleting budgets."""

    def test_update_budget_amount(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories
    ):
        # Arrange
        budget = Factory.budget(
            test_db,
            seed_account.idAccount,
            seed_categories[0].idCategory,
            Decimal("5000"),
        )
        test_db.flush()
        test_db.expire_all()

        # Act
        response = test_client.put(
            f"/api/v1/budgets/{budget.idBudget}",
            json={"amount": 7000.0},
        )

        # Assert
        assert response.status_code == 200
        assert float(response.json()["amount"]) == 7000.0

    def test_delete_budget_returns_204(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories
    ):
        # Arrange
        budget = Factory.budget(
            test_db,
            seed_account.idAccount,
            seed_categories[0].idCategory,
            Decimal("2000"),
        )
        test_db.flush()
        test_db.expire_all()

        # Act
        response = test_client.delete(f"/api/v1/budgets/{budget.idBudget}")

        # Assert
        assert response.status_code == 204

    def test_delete_nonexistent_budget_returns_404(
        self, test_client, test_db, mock_repositories
    ):
        # Act
        response = test_client.delete("/api/v1/budgets/99999")

        # Assert
        assert response.status_code == 404


class TestBudgetSummary:
    """Tests for budget summary endpoint with transaction aggregation."""

    def test_budget_summary_with_transactions(
        self,
        test_client,
        test_db,
        mock_repositories,
        seed_account,
        seed_categories,
        account_headers,
    ):
        # Arrange - create budget and transactions in the same category
        category = seed_categories[0]  # Mad
        Factory.budget(
            test_db,
            seed_account.idAccount,
            category.idCategory,
            Decimal("5000"),
        )
        Factory.transaction(
            test_db,
            seed_account.idAccount,
            category.idCategory,
            amount=Decimal("-1500"),
            description="Netto indkøb",
        )
        Factory.transaction(
            test_db,
            seed_account.idAccount,
            category.idCategory,
            amount=Decimal("-800"),
            description="Irma indkøb",
        )
        test_db.flush()
        test_db.expire_all()

        today = date.today()

        # Act
        response = test_client.get(
            "/api/v1/budgets/summary",
            params={"month": str(today.month), "year": str(today.year)},
            headers=account_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_budget"] == 5000.0
        assert data["total_spent"] == 2300.0
        assert data["total_remaining"] == 2700.0
