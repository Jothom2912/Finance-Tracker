from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _cat_payload(**overrides) -> dict:  # type: ignore[no-untyped-def]
    defaults = {
        "name": "Food",
        "type": "expense",
    }
    defaults.update(overrides)
    return defaults


class TestCreateCategory:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(),
            headers=auth_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Food"
        assert data["type"] == "expense"
        assert "id" in data

    @pytest.mark.asyncio()
    async def test_duplicate_name_returns_400(
        self, client: AsyncClient, auth_headers: dict,
    ) -> None:
        await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Transport"),
            headers=auth_headers,
        )

        resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Transport"),
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio()
    async def test_no_auth_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/categories/", json=_cat_payload())

        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_invalid_type_returns_422(
        self, client: AsyncClient, auth_headers: dict,
    ) -> None:
        resp = await client.post(
            "/api/v1/categories/",
            json={"name": "Test", "type": "invalid"},
            headers=auth_headers,
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio()
    async def test_empty_name_returns_422(
        self, client: AsyncClient, auth_headers: dict,
    ) -> None:
        resp = await client.post(
            "/api/v1/categories/",
            json={"name": "", "type": "expense"},
            headers=auth_headers,
        )

        assert resp.status_code == 422


class TestListCategories:
    @pytest.mark.asyncio()
    async def test_returns_all(self, client: AsyncClient, auth_headers: dict) -> None:
        await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Food"),
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Transport"),
            headers=auth_headers,
        )

        resp = await client.get("/api/v1/categories/", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {c["name"] for c in data}
        assert names == {"Food", "Transport"}

    @pytest.mark.asyncio()
    async def test_empty_list(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get("/api/v1/categories/", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json() == []


class TestGetCategory:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/categories/{cat_id}", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["id"] == cat_id
        assert resp.json()["name"] == "Food"

    @pytest.mark.asyncio()
    async def test_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get("/api/v1/categories/99999", headers=auth_headers)

        assert resp.status_code == 404


class TestUpdateCategory:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/categories/{cat_id}",
            json={"name": "Groceries"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Groceries"
        assert data["type"] == "expense"

    @pytest.mark.asyncio()
    async def test_change_type(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/categories/{cat_id}",
            json={"type": "income"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["type"] == "income"

    @pytest.mark.asyncio()
    async def test_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.put(
            "/api/v1/categories/99999",
            json={"name": "Nope"},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_empty_body_returns_unchanged(
        self, client: AsyncClient, auth_headers: dict,
    ) -> None:
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/categories/{cat_id}",
            json={},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Food"

    @pytest.mark.asyncio()
    async def test_duplicate_name_returns_400(
        self, client: AsyncClient, auth_headers: dict,
    ) -> None:
        await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Food"),
            headers=auth_headers,
        )
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Transport"),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/categories/{cat_id}",
            json={"name": "Food"},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]


class TestDeleteCategory:
    @pytest.mark.asyncio()
    async def test_success(self, client: AsyncClient, auth_headers: dict) -> None:
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/categories/{cat_id}", headers=auth_headers,
        )
        assert del_resp.status_code == 204

        get_resp = await client.get(
            f"/api/v1/categories/{cat_id}", headers=auth_headers,
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_not_found(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.delete(
            "/api/v1/categories/99999", headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_in_use_returns_409(
        self, client: AsyncClient, auth_headers: dict,
    ) -> None:
        create_cat = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Meals"),
            headers=auth_headers,
        )
        cat_id = create_cat.json()["id"]

        await client.post(
            "/api/v1/transactions/",
            json={
                "account_id": 100,
                "account_name": "Main",
                "category_id": cat_id,
                "category_name": "Meals",
                "amount": "25.00",
                "transaction_type": "expense",
                "date": "2026-03-01",
            },
            headers=auth_headers,
        )

        resp = await client.delete(
            f"/api/v1/categories/{cat_id}", headers=auth_headers,
        )

        assert resp.status_code == 409
        assert "cannot be deleted" in resp.json()["detail"]


class TestCategoryOutboxEvents:
    @pytest.mark.asyncio()
    async def test_create_writes_outbox(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    ) -> None:
        await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Salary", type="income"),
            headers=auth_headers,
        )

        from app.models import OutboxEventModel

        result = await db_session.execute(
            select(OutboxEventModel).where(
                OutboxEventModel.event_type == "category.created"
            )
        )
        entries = result.scalars().all()

        assert len(entries) == 1
        payload = json.loads(entries[0].payload_json)
        assert payload["name"] == "Salary"
        assert payload["category_type"] == "income"
        assert entries[0].aggregate_type == "category"

    @pytest.mark.asyncio()
    async def test_update_writes_outbox_with_previous(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    ) -> None:
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Eating Out"),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        await client.put(
            f"/api/v1/categories/{cat_id}",
            json={"name": "Dining"},
            headers=auth_headers,
        )

        from app.models import OutboxEventModel

        result = await db_session.execute(
            select(OutboxEventModel).where(
                OutboxEventModel.event_type == "category.updated"
            )
        )
        entries = result.scalars().all()

        assert len(entries) == 1
        payload = json.loads(entries[0].payload_json)
        assert payload["name"] == "Dining"
        assert payload["previous_name"] == "Eating Out"

    @pytest.mark.asyncio()
    async def test_delete_writes_outbox(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    ) -> None:
        create_resp = await client.post(
            "/api/v1/categories/",
            json=_cat_payload(name="Temp"),
            headers=auth_headers,
        )
        cat_id = create_resp.json()["id"]

        await client.delete(
            f"/api/v1/categories/{cat_id}", headers=auth_headers,
        )

        from app.models import OutboxEventModel

        result = await db_session.execute(
            select(OutboxEventModel).where(
                OutboxEventModel.event_type == "category.deleted"
            )
        )
        entries = result.scalars().all()

        assert len(entries) == 1
        payload = json.loads(entries[0].payload_json)
        assert payload["category_id"] == cat_id
        assert payload["name"] == "Temp"
