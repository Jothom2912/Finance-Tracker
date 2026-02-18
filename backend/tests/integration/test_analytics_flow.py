"""Integration tests for analytics endpoints."""

from decimal import Decimal

from .conftest import Factory


class TestDashboardAnalytics:
    def test_dashboard_overview_returns_200(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        response = test_client.get("/dashboard/overview/", headers=account_headers)

        assert response.status_code == 200
        body = response.json()
        assert "total_income" in body
        assert "total_expenses" in body
        assert "net_change_in_period" in body

    def test_dashboard_expenses_by_month_returns_200(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        expense_category = seed_categories[0]
        Factory.transaction(
            test_db,
            seed_account.idAccount,
            expense_category.idCategory,
            amount=Decimal("-500"),
            description="Transport",
            type="expense",
        )

        response = test_client.get("/dashboard/expenses-by-month/", headers=account_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)
