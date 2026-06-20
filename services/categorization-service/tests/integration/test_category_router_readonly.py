"""Fase 1 — split-brain lukket: cat-service's categories router is read-only.

Per ADR-002 transaction-service is the sole writer to the categories table.
These tests assert that the write routes (POST/PUT/DELETE) are no longer
registered on categorization-service, while the read routes that
budget-service depends on still respond.

The tests are DB-free: write methods are rejected by routing (405) before
any dependency runs, and the single read route exercised here has its
service + auth dependencies overridden with stubs.  ``TestClient`` is not
used as a context manager, so the app's startup warmup (which would hit the
DB) does not run.
"""

from __future__ import annotations

from app.adapters.inbound.category_api import category_router
from app.application.dto import CategoryResponseDTO
from app.auth import get_current_user_id
from app.dependencies import get_category_service
from app.main import app
from fastapi.testclient import TestClient


class _StubCategoryService:
    async def list_categories(self) -> list[CategoryResponseDTO]:
        return [CategoryResponseDTO(id=1, name="Mad & drikke", type="expense")]


def _client() -> TestClient:
    app.dependency_overrides[get_category_service] = lambda: _StubCategoryService()
    app.dependency_overrides[get_current_user_id] = lambda: 42
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_write_routes_are_not_registered() -> None:
    """No POST/PUT/DELETE methods exist on the categories paths."""
    methods_by_path: dict[str, set[str]] = {}
    for route in category_router.routes:
        methods_by_path.setdefault(route.path, set()).update(route.methods or set())

    # POST on the collection must be gone.
    assert "POST" not in methods_by_path.get("/api/v1/categories/", set())
    # PUT/DELETE on the item must be gone.
    item_methods = methods_by_path.get("/api/v1/categories/{category_id}", set())
    assert "PUT" not in item_methods
    assert "DELETE" not in item_methods


def test_post_category_returns_405() -> None:
    """Creating a category via cat-service is rejected (method not allowed)."""
    resp = _client().post("/api/v1/categories/", json={"name": "X", "type": "expense"})
    assert resp.status_code in (404, 405)


def test_put_category_returns_405() -> None:
    resp = _client().put("/api/v1/categories/1", json={"name": "X"})
    assert resp.status_code in (404, 405)


def test_delete_category_returns_405() -> None:
    resp = _client().delete("/api/v1/categories/1")
    assert resp.status_code in (404, 405)


def test_get_categories_still_returns_200() -> None:
    """Read route budget-service depends on still works."""
    resp = _client().get("/api/v1/categories/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == 1
    assert body[0]["name"] == "Mad & drikke"
    assert body[0]["type"] == "expense"
