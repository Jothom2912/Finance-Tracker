"""ADR-003 — categorization-service is the sole taxonomy writer.

Asserts that category AND subcategory write routes are registered and
that domain exceptions map to the documented HTTP statuses. DB-free:
service + auth dependencies are overridden with stubs, and TestClient
is not used as a context manager so startup warmup never hits the DB.

Since P2-28 the write routes live under ``/api/v1/internal`` behind
``X-Internal-API-Key``; this file asserts the status *mapping*, while
``test_taxonomy_write_auth.py`` asserts that the guard is what closes
them. Both are needed — a route can be guarded and still map a domain
exception to the wrong status.
"""

from __future__ import annotations

import pytest
from app.adapters.inbound import internal_auth
from app.application.dto import CategoryResponseDTO, SubCategoryResponseDTO
from app.auth import get_current_user_id
from app.dependencies import get_category_service
from app.domain.exceptions import (
    CategoryHasSubcategories,
    CategoryNotFound,
    DuplicateCategoryName,
    InvalidCategoryType,
    SubCategoryInUse,
)
from app.main import app
from fastapi.testclient import TestClient


class _StubCategoryService:
    async def list_categories(self) -> list[CategoryResponseDTO]:
        return [CategoryResponseDTO(id=1, name="Mad & drikke", type="expense", display_order=1)]

    async def create_category(self, dto) -> CategoryResponseDTO:  # type: ignore[no-untyped-def]
        if dto.name == "Mad & drikke":
            raise DuplicateCategoryName(dto.name)
        if dto.type == "bogus":
            raise InvalidCategoryType(dto.type)
        return CategoryResponseDTO(id=11, name=dto.name, type=dto.type, display_order=dto.display_order)

    async def update_category(self, category_id, dto) -> CategoryResponseDTO:  # type: ignore[no-untyped-def]
        if category_id == 99:
            raise CategoryNotFound(category_id)
        return CategoryResponseDTO(id=category_id, name=dto.name or "X", type="expense")

    async def delete_category(self, category_id: int) -> None:
        if category_id == 1:
            raise CategoryHasSubcategories(category_id, 4)

    async def list_all_subcategories(self) -> list[SubCategoryResponseDTO]:
        return [SubCategoryResponseDTO(id=3, name="Dagligvarer", category_id=1)]

    async def create_subcategory(self, category_id, dto):  # type: ignore[no-untyped-def]
        return SubCategoryResponseDTO(id=50, name=dto.name, category_id=category_id, is_default=False)

    async def update_subcategory(self, subcategory_id, dto):  # type: ignore[no-untyped-def]
        return SubCategoryResponseDTO(id=subcategory_id, name=dto.name or "X", category_id=1)

    async def delete_subcategory(self, subcategory_id: int) -> None:
        if subcategory_id == 32:
            raise SubCategoryInUse(subcategory_id, "it is the rule engine's fallback subcategory")


KEY = "internal-key-for-tests"
KEY_HEADER = {"X-Internal-API-Key": KEY}


@pytest.fixture(autouse=True)
def _configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard fails closed on an unset key, so these status-mapping
    tests would all be 503 without a configured one."""
    monkeypatch.setattr(internal_auth.settings, "INTERNAL_API_KEY", KEY)


def _client() -> TestClient:
    app.dependency_overrides[get_category_service] = lambda: _StubCategoryService()
    app.dependency_overrides[get_current_user_id] = lambda: 42
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_create_category_returns_201() -> None:
    resp = _client().post(
        "/api/v1/internal/categories/",
        headers=KEY_HEADER,
        json={"name": "Ferie", "type": "expense", "display_order": 11},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Ferie"
    assert resp.json()["display_order"] == 11


def test_duplicate_category_maps_to_409() -> None:
    resp = _client().post(
        "/api/v1/internal/categories/",
        headers=KEY_HEADER,
        json={"name": "Mad & drikke", "type": "expense"},
    )
    assert resp.status_code == 409


def test_invalid_type_maps_to_422() -> None:
    resp = _client().post(
        "/api/v1/internal/categories/",
        headers=KEY_HEADER,
        json={"name": "X", "type": "bogus"},
    )
    assert resp.status_code == 422


def test_update_category_not_found_maps_to_404() -> None:
    resp = _client().put("/api/v1/internal/categories/99", headers=KEY_HEADER, json={"name": "Y"})
    assert resp.status_code == 404


def test_delete_category_with_children_maps_to_409() -> None:
    resp = _client().delete("/api/v1/internal/categories/1", headers=KEY_HEADER)
    assert resp.status_code == 409


def test_create_subcategory_returns_201() -> None:
    resp = _client().post(
        "/api/v1/internal/categories/1/subcategories",
        headers=KEY_HEADER,
        json={"name": "Kaffe"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category_id"] == 1
    assert body["is_default"] is False


def test_list_all_subcategories_returns_200() -> None:
    resp = _client().get("/api/v1/subcategories/")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Dagligvarer"


def test_delete_fallback_subcategory_maps_to_409() -> None:
    resp = _client().delete("/api/v1/internal/subcategories/32", headers=KEY_HEADER)
    assert resp.status_code == 409


def test_delete_subcategory_returns_204() -> None:
    resp = _client().delete("/api/v1/internal/subcategories/3", headers=KEY_HEADER)
    assert resp.status_code == 204


def test_get_categories_still_returns_200() -> None:
    """Read route budget-service depends on keeps working."""
    resp = _client().get("/api/v1/categories/")
    assert resp.status_code == 200
    assert resp.json()[0]["display_order"] == 1
