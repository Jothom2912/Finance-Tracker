"""Integration tests for the GraphQL read gateway endpoint."""

from decimal import Decimal
from datetime import date, timedelta

import pytest

from backend.models.mysql.monthly_budget import MonthlyBudget, BudgetLine
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
        today = date.today()
        category = seed_categories[0]

        mb = MonthlyBudget(
            month=today.month, year=today.year,
            account_id=seed_account.idAccount,
        )
        test_db.add(mb)
        test_db.flush()
        line = BudgetLine(
            monthly_budget_id=mb.id,
            category_id=category.idCategory,
            amount=Decimal("5000"),
        )
        test_db.add(line)
        Factory.transaction(
            test_db, seed_account.idAccount, category.idCategory,
            amount=Decimal("-1000"), type="expense",
        )
        test_db.flush()
        test_db.expire_all()

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


class TestCurrentMonthOverviewQuery:

    def test_returns_current_month_data(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        Factory.transaction(
            test_db, seed_account.idAccount, seed_categories[2].idCategory,
            amount=Decimal("5000"), type="income",
        )
        Factory.transaction(
            test_db, seed_account.idAccount, seed_categories[0].idCategory,
            amount=Decimal("-1200"), type="expense",
        )
        test_db.flush()
        test_db.expire_all()

        query = """
        query {
            currentMonthOverview {
                startDate
                endDate
                totalIncome
                totalExpenses
                netChangeInPeriod
                expensesByCategory { categoryName amount }
                currentAccountBalance
                trend {
                    incomeChangePercent
                    expenseChangePercent
                    netChangeDiff
                    previousMonthIncome
                    previousMonthExpenses
                }
            }
        }
        """
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert "errors" not in body
        data = body["data"]["currentMonthOverview"]

        today = date.today()
        assert data["startDate"] == date(today.year, today.month, 1).isoformat()
        assert float(data["totalIncome"]) == 5000.0
        assert float(data["totalExpenses"]) == 1200.0

        trend = data["trend"]
        assert trend is not None
        assert "incomeChangePercent" in trend
        assert "expenseChangePercent" in trend
        assert "netChangeDiff" in trend
        assert float(trend["previousMonthIncome"]) >= 0
        assert float(trend["previousMonthExpenses"]) >= 0

    def test_returns_error_without_account(
        self, test_client, test_db, mock_repositories
    ):
        query = "{ currentMonthOverview { totalIncome } }"
        status, body = _gql(test_client, query)

        assert status == 200
        assert body.get("errors") is not None

    def test_returns_zero_totals_with_no_transactions(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        query = """
        query {
            currentMonthOverview {
                totalIncome
                totalExpenses
            }
        }
        """
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert "errors" not in body
        data = body["data"]["currentMonthOverview"]
        assert float(data["totalIncome"]) == 0.0
        assert float(data["totalExpenses"]) == 0.0


class TestGoalProgressQuery:

    def test_returns_goals_with_progress(
        self, test_client, test_db, mock_repositories, seed_account, account_headers
    ):
        Factory.goal(
            test_db, seed_account.idAccount,
            name="Ferie", target_amount=Decimal("10000"),
            current_amount=Decimal("3500"),
        )
        Factory.goal(
            test_db, seed_account.idAccount,
            name="Nødopsparing", target_amount=Decimal("50000"),
            current_amount=Decimal("50000"), status="completed",
        )
        test_db.flush()
        test_db.expire_all()

        query = """
        query {
            goalProgress {
                id
                name
                targetAmount
                currentAmount
                percentComplete
                status
            }
        }
        """
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert "errors" not in body
        goals = body["data"]["goalProgress"]
        assert len(goals) == 2

        ferie = next(g for g in goals if g["name"] == "Ferie")
        assert float(ferie["targetAmount"]) == 10000.0
        assert float(ferie["currentAmount"]) == 3500.0
        assert float(ferie["percentComplete"]) == 35.0

        noed = next(g for g in goals if g["name"] == "Nødopsparing")
        assert float(noed["percentComplete"]) == 100.0
        assert noed["status"] == "completed"

    def test_returns_empty_list_when_no_goals(
        self, test_client, test_db, mock_repositories, seed_account, account_headers
    ):
        query = "{ goalProgress { id name } }"
        status, body = _gql(test_client, query, headers=account_headers)

        assert status == 200
        assert "errors" not in body
        assert body["data"]["goalProgress"] == []

    def test_returns_error_without_account(
        self, test_client, test_db, mock_repositories
    ):
        query = "{ goalProgress { id } }"
        status, body = _gql(test_client, query)

        assert status == 200
        assert body.get("errors") is not None


class TestTopSpendingCategoriesQuery:

    def test_returns_top_categories_sorted_by_amount(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        Factory.transaction(
            test_db, seed_account.idAccount, seed_categories[0].idCategory,
            amount=Decimal("-3000"), type="expense",
        )
        Factory.transaction(
            test_db, seed_account.idAccount, seed_categories[1].idCategory,
            amount=Decimal("-1500"), type="expense",
        )
        test_db.flush()
        test_db.expire_all()

        today = date.today()
        query = """
        query ($month: Int!, $year: Int!, $limit: Int!) {
            topSpendingCategories(month: $month, year: $year, limit: $limit) {
                categoryName
                amount
                percentageOfTotal
            }
        }
        """
        status, body = _gql(
            test_client, query,
            variables={"month": today.month, "year": today.year, "limit": 5},
            headers=account_headers,
        )

        assert status == 200
        assert "errors" not in body
        cats = body["data"]["topSpendingCategories"]
        assert len(cats) == 2
        assert cats[0]["categoryName"] == "Mad"
        assert float(cats[0]["amount"]) == 3000.0
        assert float(cats[0]["percentageOfTotal"]) == pytest.approx(66.7, abs=0.1)

    def test_respects_limit_parameter(
        self, test_client, test_db, mock_repositories, seed_account, seed_categories, account_headers
    ):
        Factory.transaction(
            test_db, seed_account.idAccount, seed_categories[0].idCategory,
            amount=Decimal("-2000"), type="expense",
        )
        Factory.transaction(
            test_db, seed_account.idAccount, seed_categories[1].idCategory,
            amount=Decimal("-1000"), type="expense",
        )
        test_db.flush()
        test_db.expire_all()

        today = date.today()
        query = """
        query ($month: Int!, $year: Int!, $limit: Int!) {
            topSpendingCategories(month: $month, year: $year, limit: $limit) {
                categoryName
            }
        }
        """
        status, body = _gql(
            test_client, query,
            variables={"month": today.month, "year": today.year, "limit": 1},
            headers=account_headers,
        )

        assert status == 200
        assert "errors" not in body
        assert len(body["data"]["topSpendingCategories"]) == 1

    def test_returns_error_without_account(
        self, test_client, test_db, mock_repositories
    ):
        today = date.today()
        query = """
        query ($month: Int!, $year: Int!) {
            topSpendingCategories(month: $month, year: $year) {
                categoryName
            }
        }
        """
        status, body = _gql(
            test_client, query,
            variables={"month": today.month, "year": today.year},
        )

        assert status == 200
        assert body.get("errors") is not None


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
