"""Integration tests for the GraphQL read gateway endpoint."""

from decimal import Decimal
from datetime import date

import pytest

from .conftest import Factory


GRAPHQL_URL = "/api/v1/graphql"


def _gql(client, query: str, variables: dict | None = None, headers: dict | None = None):
    """Send a GraphQL POST request and return (status_code, json_body)."""
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = client.post(GRAPHQL_URL, json=payload, headers=headers or {})
    return resp.status_code, resp.json()


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------


class TestFinancialOverviewQuery:

    def test_returns_overview_with_valid_account(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        query = """
        query {
            financialOverview {
                startDate
                endDate
                totalIncome
                totalExpenses
                netChangeInPeriod
                expensesByCategory { categoryName amount }
            }
        }
        """
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert "errors" not in body
        data = body["data"]["financialOverview"]
        assert "totalIncome" in data
        assert "totalExpenses" in data
        assert isinstance(data["expensesByCategory"], list)

    def test_returns_error_without_account(
        self, test_client, test_db, mock_repositories
    ):
        query = "{ financialOverview { totalIncome } }"
        status, body = _gql(test_client, query)

        assert status == 200
        assert body.get("errors") is not None


class TestExpensesByMonthQuery:

    def test_returns_monthly_expenses(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        Factory.transaction(
            test_db,
            seed_account.idAccount,
            seed_categories[0].idCategory,
            amount=Decimal("-300"),
            type="expense",
        )

        query = """
        query {
            expensesByMonth {
                month
                totalExpenses
            }
        }
        """
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert "errors" not in body
        data = body["data"]["expensesByMonth"]
        assert isinstance(data, list)


class TestBudgetSummaryQuery:

    def test_returns_budget_summary(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        category = seed_categories[0]
        Factory.budget(test_db, seed_account.idAccount, category.idCategory, Decimal("5000"))
        Factory.transaction(
            test_db, seed_account.idAccount, category.idCategory,
            amount=Decimal("-1000"), type="expense",
        )
        test_db.flush()
        test_db.expire_all()

        today = date.today()
        query = """
        query ($month: Int!, $year: Int!) {
            budgetSummary(month: $month, year: $year) {
                month
                year
                totalBudget
                totalSpent
                totalRemaining
                overBudgetCount
                items { categoryName budgetAmount spentAmount }
            }
        }
        """
        status, body = _gql(
            test_client, query,
            variables={"month": today.month, "year": today.year},
            headers=account_headers,
        )

        assert status == 200
        assert "errors" not in body
        data = body["data"]["budgetSummary"]
        assert float(data["totalBudget"]) == 5000.0


# ---------------------------------------------------------------------------
# Cross-context read queries
# ---------------------------------------------------------------------------


class TestCategoriesQuery:

    def test_returns_all_categories(
        self, test_client, test_db, mock_repositories, seed_categories
    ):
        query = "{ categories { id name type } }"
        status, body = _gql(test_client, query)

        assert status == 200
        assert "errors" not in body
        categories = body["data"]["categories"]
        assert len(categories) >= 3
        names = {c["name"] for c in categories}
        assert "Mad" in names
        assert "Transport" in names


class TestTransactionsQuery:

    def test_returns_transactions_for_account(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        Factory.transaction(
            test_db, seed_account.idAccount, seed_categories[0].idCategory,
            amount=Decimal("-250"), description="Test GQL tx", type="expense",
        )
        test_db.flush()
        test_db.expire_all()

        query = """
        query {
            transactions(limit: 10) {
                id
                amount
                description
                date
                type
                categoryId
                accountId
            }
        }
        """
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert "errors" not in body
        txs = body["data"]["transactions"]
        assert len(txs) >= 1
        assert txs[0]["description"] == "Test GQL tx"


# ---------------------------------------------------------------------------
# Schema validation (demonstrates GraphQL advantage over REST)
# ---------------------------------------------------------------------------


class TestSchemaValidation:

    def test_invalid_field_name_returns_error(
        self, test_client, test_db, mock_repositories, seed_categories
    ):
        query = "{ categories { id name nonExistentField } }"
        status, body = _gql(test_client, query)

        assert status == 200
        assert body.get("errors") is not None
        error_msg = body["errors"][0]["message"]
        assert "nonExistentField" in error_msg

    def test_invalid_query_name_returns_error(
        self, test_client, test_db, mock_repositories
    ):
        query = "{ unknownQuery { id } }"
        status, body = _gql(test_client, query)

        assert status == 200
        assert body.get("errors") is not None

    def test_missing_required_argument_returns_error(
        self, test_client, test_db, mock_repositories, account_headers
    ):
        query = "{ budgetSummary { month year } }"
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert body.get("errors") is not None

    def test_mutations_not_available(
        self, test_client, test_db, mock_repositories
    ):
        query = """
        mutation {
            createTransaction(amount: 100) { id }
        }
        """
        status, body = _gql(test_client, query)

        assert status == 200
        assert body.get("errors") is not None


# ---------------------------------------------------------------------------
# Correlation ID in responses
# ---------------------------------------------------------------------------


class TestCorrelationId:

    def test_response_includes_correlation_id_header(
        self, test_client, test_db, mock_repositories
    ):
        response = test_client.get("/health")
        assert "x-correlation-id" in response.headers

    def test_custom_correlation_id_is_echoed_back(
        self, test_client, test_db, mock_repositories
    ):
        custom_id = "test-correlation-12345"
        response = test_client.get(
            "/health", headers={"X-Correlation-ID": custom_id}
        )
        assert response.headers.get("x-correlation-id") == custom_id

    def test_graphql_response_includes_correlation_id(
        self, test_client, test_db, mock_repositories, seed_categories
    ):
        resp = test_client.post(
            GRAPHQL_URL,
            json={"query": "{ categories { id name } }"},
        )
        assert "x-correlation-id" in resp.headers
