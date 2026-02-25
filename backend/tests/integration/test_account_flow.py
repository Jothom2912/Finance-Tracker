"""Integration tests for account flows (HTTP -> Service -> Repository -> DB)."""

import pytest
from decimal import Decimal

from .conftest import Factory


class TestAccountCreation:
    """Tests for creating accounts through the API."""

    def test_create_account_returns_201(
        self, test_client, test_db, mock_repositories, auth_headers
    ):
        # Act
        response = test_client.post(
            "/api/v1/accounts/",
            json={"name": "Opsparingskonto", "saldo": 25000.0},
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == 201, response.json()
        data = response.json()
        assert data["name"] == "Opsparingskonto"
        assert float(data["saldo"]) == 25000.0

    def test_create_account_without_auth_returns_401(
        self, test_client, test_db, mock_repositories
    ):
        # Act - no Authorization header
        response = test_client.post(
            "/api/v1/accounts/",
            json={"name": "Unauthorized", "saldo": 1000.0},
        )

        # Assert
        assert response.status_code == 401

    def test_create_multiple_accounts(
        self, test_client, test_db, mock_repositories, auth_headers
    ):
        # Act
        r1 = test_client.post(
            "/api/v1/accounts/",
            json={"name": "Konto 1", "saldo": 5000.0},
            headers=auth_headers,
        )
        r2 = test_client.post(
            "/api/v1/accounts/",
            json={"name": "Konto 2", "saldo": 10000.0},
            headers=auth_headers,
        )

        # Assert
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["name"] == "Konto 1"
        assert r2.json()["name"] == "Konto 2"


class TestAccountRetrieval:
    """Tests for fetching accounts."""

    def test_get_accounts_returns_user_accounts(
        self, test_client, test_db, mock_repositories, auth_headers, seed_account
    ):
        # Act
        response = test_client.get("/api/v1/accounts/", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # seed_account was created for the seed_user
        assert len(data) >= 1
        account_names = [a["name"] for a in data]
        assert "Lønkonto" in account_names

    def test_get_accounts_without_auth_returns_401(
        self, test_client, test_db, mock_repositories
    ):
        # Act
        response = test_client.get("/api/v1/accounts/")

        # Assert
        assert response.status_code == 401

    def test_get_account_by_id_returns_200(
        self, test_client, test_db, mock_repositories, auth_headers, seed_account
    ):
        # Act
        response = test_client.get(
            f"/api/v1/accounts/{seed_account.idAccount}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Lønkonto"

    def test_get_nonexistent_account_returns_404(
        self, test_client, test_db, mock_repositories, auth_headers
    ):
        # Act
        response = test_client.get("/api/v1/accounts/99999", headers=auth_headers)

        # Assert
        assert response.status_code == 404


class TestAccountUpdate:
    """Tests for updating accounts."""

    def test_update_account_name_and_saldo(
        self, test_client, test_db, mock_repositories, auth_headers, seed_account
    ):
        # Act
        response = test_client.put(
            f"/api/v1/accounts/{seed_account.idAccount}",
            json={"name": "Updated Konto", "saldo": 15000.0},
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Konto"
        assert float(data["saldo"]) == 15000.0

    def test_update_account_without_auth_returns_401(
        self, test_client, test_db, mock_repositories, seed_account
    ):
        # Act
        response = test_client.put(
            f"/api/v1/accounts/{seed_account.idAccount}",
            json={"name": "Hack", "saldo": 999999.0},
        )

        # Assert
        assert response.status_code == 401
