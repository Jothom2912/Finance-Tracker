from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _tx_payload(**overrides) -> dict:  # type: ignore[no-untyped-def]
    defaults = {
        "account_id": 100,
        "account_name": "Main Account",
        "category_id": 5,
        "category_name": "Food",
        "amount": "49.99",
        "transaction_type": "expense",
        "description": "Groceries",
        "date": "2026-03-01",
    }
    defaults.update(overrides)
    return defaults


def _planned_payload(**overrides) -> dict:  # type: ignore[no-untyped-def]
    defaults = {
        "account_id": 100,
        "account_name": "Main Account",
        "category_id": 5,
        "category_name": "Rent",
        "amount": "5000.00",
        "transaction_type": "expense",
        "description": "Monthly rent",
        "recurrence": "monthly",
        "next_execution": "2026-04-01",
    }
    defaults.update(overrides)
    return defaults


# ── Transaction CRUD ────────────────────────────────────────────────


class TestCreateTransaction:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["account_name"] == "Main Account"
        assert Decimal(data["amount"]) == Decimal("49.99")
        assert data["transaction_type"] == "expense"
        assert data["user_id"] == 1

    @pytest.mark.asyncio()
    async def test_no_auth_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/transactions/", json=_tx_payload())

        assert resp.status_code == 401


class TestGetTransaction:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["id"] == tx_id

    @pytest.mark.asyncio()
    async def test_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get("/api/v1/transactions/99999", headers=auth_headers)

        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_wrong_user_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        user2_headers: dict,
    ) -> None:
        """User 2 cannot see user 1's transaction — data isolation."""
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/transactions/{tx_id}", headers=user2_headers)

        assert resp.status_code == 404


class TestListTransactions:
    @pytest.mark.asyncio()
    async def test_returns_all_for_user(self, client: AsyncClient, auth_headers: dict) -> None:
        for i in range(3):
            await client.post(
                "/api/v1/transactions/",
                json=_tx_payload(description=f"tx-{i}"),
                headers=auth_headers,
            )

        resp = await client.get("/api/v1/transactions/", headers=auth_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio()
    async def test_filter_by_account(self, client: AsyncClient, auth_headers: dict) -> None:
        await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(account_id=100, account_name="A"),
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(account_id=200, account_name="B"),
            headers=auth_headers,
        )

        resp = await client.get("/api/v1/transactions/?account_id=100", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["account_id"] == 100

    @pytest.mark.asyncio()
    async def test_filter_by_date_range(self, client: AsyncClient, auth_headers: dict) -> None:
        await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(date="2026-01-15"),
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(date="2026-06-15"),
            headers=auth_headers,
        )

        resp = await client.get(
            "/api/v1/transactions/?start_date=2026-01-01&end_date=2026-03-31",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestUpdateTransaction:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/transactions/{tx_id}",
            json={"amount": "75.00", "description": "Updated"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert Decimal(data["amount"]) == Decimal("75.00")
        assert data["description"] == "Updated"
        assert data["transaction_type"] == "expense"

    @pytest.mark.asyncio()
    async def test_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.put(
            "/api/v1/transactions/99999",
            json={"amount": "75.00"},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_wrong_user_returns_404(
        self, client: AsyncClient, auth_headers: dict, user2_headers: dict,
    ) -> None:
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/transactions/{tx_id}",
            json={"amount": "75.00"},
            headers=user2_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_empty_body_returns_unchanged(
        self, client: AsyncClient, auth_headers: dict,
    ) -> None:
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/transactions/{tx_id}",
            json={},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert Decimal(data["amount"]) == Decimal("49.99")

    @pytest.mark.asyncio()
    async def test_writes_outbox_event(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
    ) -> None:
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        await client.put(
            f"/api/v1/transactions/{tx_id}",
            json={"amount": "75.00"},
            headers=auth_headers,
        )

        from app.models import OutboxEventModel

        result = await db_session.execute(
            select(OutboxEventModel).where(OutboxEventModel.event_type == "transaction.updated")
        )
        entries = result.scalars().all()

        assert len(entries) == 1
        payload = json.loads(entries[0].payload_json)
        assert payload["amount"] == "75.00"
        assert payload["previous_amount"] == "49.99"


class TestDeleteTransaction:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_writes_outbox_event(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
    ) -> None:
        create_resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )
        tx_id = create_resp.json()["id"]

        await client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)

        from app.models import OutboxEventModel

        result = await db_session.execute(
            select(OutboxEventModel).where(OutboxEventModel.event_type == "transaction.deleted")
        )
        entries = result.scalars().all()

        assert len(entries) == 1
        assert entries[0].aggregate_type == "transaction"
        assert entries[0].status == "pending"
        payload = json.loads(entries[0].payload_json)
        assert payload["transaction_id"] == tx_id


# ── CSV Import ──────────────────────────────────────────────────────


class TestCSVImport:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        csv = (
            "date,amount,transaction_type,account_id,account_name,"
            "category_id,category_name,description\n"
            "2026-03-01,49.99,expense,100,Main Account,5,Food,Groceries\n"
            "2026-03-02,120.00,income,100,Main Account,6,Salary,March pay\n"
        )

        resp = await client.post(
            "/api/v1/transactions/import-csv",
            files={"file": ("data.csv", csv, "text/csv")},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["skipped"] == 0

    @pytest.mark.asyncio()
    async def test_partial_errors(self, client: AsyncClient, auth_headers: dict) -> None:
        csv = (
            "date,amount,transaction_type,account_id,account_name\n"
            "2026-03-01,49.99,expense,100,Main Account\n"
            "2026-03-02,INVALID,expense,100,Main Account\n"
        )

        resp = await client.post(
            "/api/v1/transactions/import-csv",
            files={"file": ("data.csv", csv, "text/csv")},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 1
        assert data["skipped"] == 1
        assert len(data["errors"]) == 1


# ── Planned Transactions ────────────────────────────────────────────


class TestPlannedTransactions:
    @pytest.mark.asyncio()
    async def test_create(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.post(
            "/api/v1/planned-transactions/",
            json=_planned_payload(),
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["recurrence"] == "monthly"
        assert data["is_active"] is True

    @pytest.mark.asyncio()
    async def test_list_active_only(self, client: AsyncClient, auth_headers: dict) -> None:
        await client.post(
            "/api/v1/planned-transactions/",
            json=_planned_payload(description="active"),
            headers=auth_headers,
        )
        create_resp = await client.post(
            "/api/v1/planned-transactions/",
            json=_planned_payload(description="to-deactivate"),
            headers=auth_headers,
        )
        deactivate_id = create_resp.json()["id"]
        await client.delete(
            f"/api/v1/planned-transactions/{deactivate_id}",
            headers=auth_headers,
        )

        resp = await client.get(
            "/api/v1/planned-transactions/?active_only=true",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["description"] == "active"

    @pytest.mark.asyncio()
    async def test_update(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/planned-transactions/",
            json=_planned_payload(),
            headers=auth_headers,
        )
        planned_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/planned-transactions/{planned_id}",
            json={"amount": "6000.00"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert Decimal(resp.json()["amount"]) == Decimal("6000.00")

    @pytest.mark.asyncio()
    async def test_deactivate(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/planned-transactions/",
            json=_planned_payload(),
            headers=auth_headers,
        )
        planned_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/planned-transactions/{planned_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 204


# ── Event Publishing ────────────────────────────────────────────────


class TestCrossServiceJWT:
    @pytest.mark.asyncio()
    async def test_monolith_format_token_accepted(self, client: AsyncClient) -> None:
        """A token using the monolith payload format (user_id claim)
        must be accepted by transaction-service.
        """
        from tests.integration.conftest import TEST_ALGORITHM, TEST_SECRET

        monolith_token = jwt.encode(
            {
                "user_id": 1,
                "username": "alice",
                "email": "alice@example.com",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            TEST_SECRET,
            algorithm=TEST_ALGORITHM,
        )
        headers = {"Authorization": f"Bearer {monolith_token}"}

        resp = await client.get("/api/v1/transactions/", headers=headers)

        assert resp.status_code == 200


# ── Event Publishing ────────────────────────────────────────────────


class TestEventPublishing:
    @pytest.mark.asyncio()
    async def test_create_writes_outbox_event(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
    ) -> None:
        resp = await client.post(
            "/api/v1/transactions/",
            json=_tx_payload(),
            headers=auth_headers,
        )

        assert resp.status_code == 201

        from app.models import OutboxEventModel

        result = await db_session.execute(
            select(OutboxEventModel).where(OutboxEventModel.event_type == "transaction.created")
        )
        entries = result.scalars().all()

        assert len(entries) == 1
        assert entries[0].aggregate_type == "transaction"
        assert entries[0].status == "pending"
        payload = json.loads(entries[0].payload_json)
        assert payload["amount"] == "49.99"
        assert payload["user_id"] == 1
