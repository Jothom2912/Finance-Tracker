"""Integration tests for Account API endpoints."""

from unittest.mock import patch

from tests.conftest import _make_auth_header


class TestAccountCRUD:
    def test_create_account(self, client):
        with patch("app.adapters.outbound.user_adapter.UserServiceAdapter.exists", return_value=True):
            resp = client.post(
                "/api/v1/accounts/",
                json={"name": "Min konto", "saldo": 1000.50, "budget_start_day": 15},
                headers=_make_auth_header(user_id=1),
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Min konto"
        assert data["saldo"] == 1000.50
        assert data["budget_start_day"] == 15
        assert data["User_idUser"] == 1

    def test_create_account_preserves_budget_start_day(self, client):
        with patch("app.adapters.outbound.user_adapter.UserServiceAdapter.exists", return_value=True):
            resp = client.post(
                "/api/v1/accounts/",
                json={"name": "Budgetkonto", "saldo": 0, "budget_start_day": 25},
                headers=_make_auth_header(user_id=1),
            )
        assert resp.status_code == 201
        assert resp.json()["budget_start_day"] == 25

    def test_list_accounts_returns_own(self, client):
        with patch("app.adapters.outbound.user_adapter.UserServiceAdapter.exists", return_value=True):
            client.post(
                "/api/v1/accounts/",
                json={"name": "Konto1", "saldo": 0},
                headers=_make_auth_header(user_id=1),
            )
            client.post(
                "/api/v1/accounts/",
                json={"name": "Konto2", "saldo": 0},
                headers=_make_auth_header(user_id=1),
            )
        resp = client.get("/api/v1/accounts/", headers=_make_auth_header(user_id=1))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_accounts_isolates_users(self, client):
        with patch("app.adapters.outbound.user_adapter.UserServiceAdapter.exists", return_value=True):
            client.post(
                "/api/v1/accounts/",
                json={"name": "User1 konto", "saldo": 0},
                headers=_make_auth_header(user_id=1),
            )
            client.post(
                "/api/v1/accounts/",
                json={"name": "User2 konto", "saldo": 0},
                headers=_make_auth_header(user_id=2),
            )
        resp = client.get("/api/v1/accounts/", headers=_make_auth_header(user_id=2))
        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) == 1
        assert accounts[0]["name"] == "User2 konto"

    def test_get_account_forbidden_for_other_user(self, client):
        with patch("app.adapters.outbound.user_adapter.UserServiceAdapter.exists", return_value=True):
            create_resp = client.post(
                "/api/v1/accounts/",
                json={"name": "Privat", "saldo": 0},
                headers=_make_auth_header(user_id=1),
            )
        account_id = create_resp.json()["idAccount"]
        resp = client.get(f"/api/v1/accounts/{account_id}", headers=_make_auth_header(user_id=2))
        assert resp.status_code == 403

    def test_update_account(self, client):
        with patch("app.adapters.outbound.user_adapter.UserServiceAdapter.exists", return_value=True):
            create_resp = client.post(
                "/api/v1/accounts/",
                json={"name": "Original", "saldo": 100},
                headers=_make_auth_header(user_id=1),
            )
        account_id = create_resp.json()["idAccount"]
        resp = client.put(
            f"/api/v1/accounts/{account_id}",
            json={"name": "Opdateret", "saldo": 200, "budget_start_day": 10},
            headers=_make_auth_header(user_id=1),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Opdateret"
        assert resp.json()["saldo"] == 200.0
        assert resp.json()["budget_start_day"] == 10

    def test_create_account_rejects_nonexistent_user(self, client):
        with patch("app.adapters.outbound.user_adapter.UserServiceAdapter.exists", return_value=False):
            resp = client.post(
                "/api/v1/accounts/",
                json={"name": "Konto", "saldo": 0},
                headers=_make_auth_header(user_id=999),
            )
        assert resp.status_code == 400

    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/v1/accounts/")
        assert resp.status_code == 401


class TestAccountGroupCRUD:
    def test_create_group(self, client):
        with patch(
            "app.adapters.outbound.user_adapter.UserServiceAdapter.get_users_by_ids", return_value=[(1, "alice")]
        ):
            resp = client.post(
                "/api/v1/account-groups/",
                json={"name": "Familie", "max_users": 5, "user_ids": [1]},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Familie"
        assert data["max_users"] == 5

    def test_create_group_persists_users(self, client):
        with patch(
            "app.adapters.outbound.user_adapter.UserServiceAdapter.get_users_by_ids",
            return_value=[(1, "alice"), (2, "bob")],
        ):
            create_resp = client.post(
                "/api/v1/account-groups/",
                json={"name": "Par", "max_users": 5, "user_ids": [1, 2]},
            )
        group_id = create_resp.json()["idAccountGroups"]

        with patch(
            "app.adapters.outbound.user_adapter.UserServiceAdapter.get_users_by_ids",
            return_value=[(1, "alice"), (2, "bob")],
        ):
            resp = client.get(f"/api/v1/account-groups/{group_id}")
        assert resp.status_code == 200
        users = resp.json()["users"]
        assert len(users) == 2

    def test_create_group_rejects_invalid_users(self, client):
        with patch(
            "app.adapters.outbound.user_adapter.UserServiceAdapter.get_users_by_ids",
            return_value=[(1, "alice")],
        ):
            resp = client.post(
                "/api/v1/account-groups/",
                json={"name": "Ugyldig", "max_users": 5, "user_ids": [1, 999]},
            )
        assert resp.status_code == 400


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "account-service"
