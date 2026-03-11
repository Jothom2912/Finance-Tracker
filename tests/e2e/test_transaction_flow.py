"""End-to-end tests for transaction-service within the full docker-compose stack.

Verifies:
- Cross-service JWT: token from user-service (8001) accepted by transaction-service (8002)
- Transaction CRUD via HTTP
- CSV import
- Planned transaction lifecycle
- Data isolation between users

Prerequisites:
    docker compose up -d --build --wait

Run:
    pytest tests/e2e/test_transaction_flow.py -v -m e2e
"""
from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio

USER_SERVICE = "http://localhost:8001/api/v1/users"
TX_SERVICE = "http://localhost:8002/api/v1"

pytestmark = pytest.mark.e2e


# ── helpers ─────────────────────────────────────────────────────────


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(
    client: httpx.AsyncClient,
) -> str:
    """Register a fresh user via user-service and return a JWT token."""
    uid = uuid.uuid4().hex[:8]
    reg = await client.post(
        f"{USER_SERVICE}/register",
        json={
            "username": f"txe2e_{uid}",
            "email": f"txe2e_{uid}@example.com",
            "password": "SecurePass123!",
        },
    )
    assert reg.status_code == 201

    login = await client.post(
        f"{USER_SERVICE}/login",
        json={
            "email": f"txe2e_{uid}@example.com",
            "password": "SecurePass123!",
        },
    )
    assert login.status_code == 200
    return login.json()["access_token"]


@pytest_asyncio.fixture
async def token() -> str:
    async with httpx.AsyncClient() as client:
        return await _register_and_login(client)


# ── health ──────────────────────────────────────────────────────────


class TestHealthCheck:
    @pytest.mark.asyncio()
    async def test_transaction_service_healthy(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8002/health")

        assert resp.status_code == 200
        assert resp.json()["service"] == "transaction-service"


# ── cross-service JWT ───────────────────────────────────────────────


class TestCrossServiceAuth:
    @pytest.mark.asyncio()
    async def test_user_service_token_accepted(
        self, token: str
    ) -> None:
        """Token issued by user-service (8001) works on transaction-service (8002)."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{TX_SERVICE}/transactions/", headers=_auth(token)
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio()
    async def test_no_token_returns_401(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{TX_SERVICE}/transactions/")

        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_invalid_token_returns_401(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{TX_SERVICE}/transactions/",
                headers=_auth("garbage.token.here"),
            )

        assert resp.status_code == 401


# ── transaction CRUD ────────────────────────────────────────────────


class TestTransactionCRUD:
    @pytest.mark.asyncio()
    async def test_create_and_get(self, token: str) -> None:
        headers = _auth(token)
        async with httpx.AsyncClient() as client:
            create_resp = await client.post(
                f"{TX_SERVICE}/transactions/",
                headers=headers,
                json={
                    "account_id": 1,
                    "account_name": "Default Account",
                    "category_id": 1,
                    "category_name": "Groceries",
                    "amount": "125.50",
                    "transaction_type": "expense",
                    "description": "Weekly groceries",
                    "date": "2025-01-15",
                },
            )
            assert create_resp.status_code == 201
            tx = create_resp.json()
            assert float(tx["amount"]) == 125.50
            assert tx["account_name"] == "Default Account"
            assert tx["category_name"] == "Groceries"
            tx_id = tx["id"]

            get_resp = await client.get(
                f"{TX_SERVICE}/transactions/{tx_id}", headers=headers
            )
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == tx_id

    @pytest.mark.asyncio()
    async def test_list_with_date_filter(self, token: str) -> None:
        headers = _auth(token)
        async with httpx.AsyncClient() as client:
            for d in ["2025-01-10", "2025-06-15"]:
                await client.post(
                    f"{TX_SERVICE}/transactions/",
                    headers=headers,
                    json={
                        "account_id": 1,
                        "account_name": "Default",
                        "amount": "50.00",
                        "transaction_type": "expense",
                        "date": d,
                    },
                )

            resp = await client.get(
                f"{TX_SERVICE}/transactions/",
                headers=headers,
                params={
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-31",
                },
            )

        assert resp.status_code == 200
        assert all(
            tx["date"].startswith("2025-01") for tx in resp.json()
        )

    @pytest.mark.asyncio()
    async def test_delete(self, token: str) -> None:
        headers = _auth(token)
        async with httpx.AsyncClient() as client:
            create_resp = await client.post(
                f"{TX_SERVICE}/transactions/",
                headers=headers,
                json={
                    "account_id": 1,
                    "account_name": "Test",
                    "amount": "10.00",
                    "transaction_type": "income",
                    "date": "2025-03-01",
                },
            )
            tx_id = create_resp.json()["id"]

            del_resp = await client.delete(
                f"{TX_SERVICE}/transactions/{tx_id}", headers=headers
            )
            assert del_resp.status_code == 204

            get_resp = await client.get(
                f"{TX_SERVICE}/transactions/{tx_id}", headers=headers
            )
            assert get_resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_data_isolation_between_users(self) -> None:
        """User A cannot see user B's transactions — returns 404, not 403."""
        async with httpx.AsyncClient() as client:
            token_a = await _register_and_login(client)
            token_b = await _register_and_login(client)

            create_resp = await client.post(
                f"{TX_SERVICE}/transactions/",
                headers=_auth(token_a),
                json={
                    "account_id": 1,
                    "account_name": "A's Account",
                    "amount": "100.00",
                    "transaction_type": "income",
                    "date": "2025-01-01",
                },
            )
            tx_id = create_resp.json()["id"]

            resp = await client.get(
                f"{TX_SERVICE}/transactions/{tx_id}",
                headers=_auth(token_b),
            )

        assert resp.status_code == 404


# ── CSV import ──────────────────────────────────────────────────────


class TestCSVImport:
    @pytest.mark.asyncio()
    async def test_import_creates_transactions(self, token: str) -> None:
        headers = _auth(token)
        csv_content = (
            "date,amount,transaction_type,description,"
            "account_id,account_name,category_id,category_name\n"
            "2025-01-01,50.00,expense,Groceries,1,Default Account,1,Food\n"
            "2025-01-02,1500.00,income,Salary,1,Default Account,,\n"
            "2025-01-03,25.50,expense,Coffee,1,Default Account,2,Cafe\n"
        )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TX_SERVICE}/transactions/import-csv",
                headers=headers,
                files={
                    "file": ("data.csv", csv_content, "text/csv")
                },
            )

            assert resp.status_code == 200
            result = resp.json()
            assert result["imported"] == 3
            assert result["skipped"] == 0
            assert result["errors"] == []

            list_resp = await client.get(
                f"{TX_SERVICE}/transactions/", headers=headers
            )
            assert len(list_resp.json()) >= 3


# ── planned transactions ────────────────────────────────────────────


class TestPlannedTransactions:
    @pytest.mark.asyncio()
    async def test_full_lifecycle(self, token: str) -> None:
        """Create → list → update → deactivate → verify gone from active list."""
        headers = _auth(token)

        async with httpx.AsyncClient() as client:
            create_resp = await client.post(
                f"{TX_SERVICE}/planned-transactions/",
                headers=headers,
                json={
                    "account_id": 1,
                    "account_name": "Default Account",
                    "amount": "500.00",
                    "transaction_type": "expense",
                    "description": "Monthly rent",
                    "recurrence": "monthly",
                    "next_execution": "2025-02-01",
                },
            )
            assert create_resp.status_code == 201
            planned_id = create_resp.json()["id"]

            list_resp = await client.get(
                f"{TX_SERVICE}/planned-transactions/",
                headers=headers,
                params={"active_only": "true"},
            )
            assert list_resp.status_code == 200
            assert any(
                p["id"] == planned_id for p in list_resp.json()
            )

            update_resp = await client.patch(
                f"{TX_SERVICE}/planned-transactions/{planned_id}",
                headers=headers,
                json={"amount": "550.00"},
            )
            assert update_resp.status_code == 200
            assert float(update_resp.json()["amount"]) == 550.0

            del_resp = await client.delete(
                f"{TX_SERVICE}/planned-transactions/{planned_id}",
                headers=headers,
            )
            assert del_resp.status_code == 204

            list_resp2 = await client.get(
                f"{TX_SERVICE}/planned-transactions/",
                headers=headers,
                params={"active_only": "true"},
            )
            assert not any(
                p["id"] == planned_id for p in list_resp2.json()
            )
