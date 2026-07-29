"""P2-28 — taxonomy writes are S2S-only; a user JWT is not enough.

Before this, any authenticated user could ``PUT /api/v1/categories/{id}``.
Measured against the dev stack 2026-07-29: a user registered one minute
earlier, owning zero transactions, renamed a category and
``propagate_category_rename`` rewrote ``category_name`` on 150 documents
across 23 *other* users in Elasticsearch. No "in use" guard can catch a
rename, because nothing is orphaned — so the fix is authorization, not a
domain guard.

DB-free, modelled on ``test_categorize_router_auth.py``: the service
dependency is overridden with a stub and TestClient is not used as a
context manager, so startup warmup never hits the DB.
"""

from __future__ import annotations

import pytest
from app.adapters.inbound import internal_auth
from app.application.dto import CategoryResponseDTO, SubCategoryResponseDTO
from app.auth import get_current_user_id
from app.dependencies import get_category_service
from app.main import app
from fastapi.testclient import TestClient

KEY = "internal-key-for-tests"
KEY_HEADER = {"X-Internal-API-Key": KEY}

# The six write routes, as (method, path, body). Kept as data rather than
# as six test functions so that a seventh write route added to the router
# without being listed here is visible as a gap.
WRITE_ROUTES = [
    ("post", "/api/v1/internal/categories/", {"name": "Ferie", "type": "expense"}),
    ("put", "/api/v1/internal/categories/1", {"name": "Omdoebt"}),
    ("delete", "/api/v1/internal/categories/2", None),
    ("post", "/api/v1/internal/categories/1/subcategories", {"name": "Kaffe"}),
    ("put", "/api/v1/internal/subcategories/3", {"name": "Omdoebt"}),
    ("delete", "/api/v1/internal/subcategories/3", None),
]

READ_ROUTES = [
    "/api/v1/categories/",
    "/api/v1/categories/1",
    "/api/v1/categories/1/subcategories",
    "/api/v1/subcategories/",
]


class _StubCategoryService:
    async def list_categories(self) -> list[CategoryResponseDTO]:
        return [CategoryResponseDTO(id=1, name="Mad & drikke", type="expense", display_order=1)]

    async def get_category(self, category_id: int) -> CategoryResponseDTO:
        return CategoryResponseDTO(id=category_id, name="Mad & drikke", type="expense")

    async def list_subcategories(self, category_id: int) -> list[SubCategoryResponseDTO]:
        return [SubCategoryResponseDTO(id=3, name="Dagligvarer", category_id=category_id)]

    async def list_all_subcategories(self) -> list[SubCategoryResponseDTO]:
        return [SubCategoryResponseDTO(id=3, name="Dagligvarer", category_id=1)]

    async def create_category(self, dto) -> CategoryResponseDTO:  # type: ignore[no-untyped-def]
        return CategoryResponseDTO(id=11, name=dto.name, type=dto.type)

    async def update_category(self, category_id, dto) -> CategoryResponseDTO:  # type: ignore[no-untyped-def]
        return CategoryResponseDTO(id=category_id, name=dto.name or "X", type="expense")

    async def delete_category(self, category_id: int) -> None:
        return None

    async def create_subcategory(self, category_id, dto):  # type: ignore[no-untyped-def]
        return SubCategoryResponseDTO(id=50, name=dto.name, category_id=category_id)

    async def update_subcategory(self, subcategory_id, dto):  # type: ignore[no-untyped-def]
        return SubCategoryResponseDTO(id=subcategory_id, name=dto.name or "X", category_id=1)

    async def delete_subcategory(self, subcategory_id: int) -> None:
        return None


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(internal_auth.settings, "INTERNAL_API_KEY", KEY)
    app.dependency_overrides[get_category_service] = lambda: _StubCategoryService()
    # A *valid* user token, in the only form these tests can express one:
    # the JWT dependency resolves successfully to user 42. Every 401 below
    # is therefore an authorization result, not a failure to authenticate.
    app.dependency_overrides[get_current_user_id] = lambda: 42
    yield TestClient(app)
    app.dependency_overrides.clear()


def _call(client: TestClient, method: str, path: str, body, headers=None):  # type: ignore[no-untyped-def]
    kwargs = {"headers": headers or {}}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(path, **kwargs)


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ROUTES)
def test_write_without_key_is_401(client: TestClient, method: str, path: str, body) -> None:  # type: ignore[no-untyped-def]
    assert _call(client, method, path, body).status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ROUTES)
def test_write_with_wrong_key_is_401(client: TestClient, method: str, path: str, body) -> None:  # type: ignore[no-untyped-def]
    resp = _call(client, method, path, body, headers={"X-Internal-API-Key": "wrong"})
    assert resp.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ROUTES)
def test_user_jwt_alone_is_not_enough(client: TestClient, method: str, path: str, body) -> None:  # type: ignore[no-untyped-def]
    """The actual regression. ``get_current_user_id`` is overridden to
    resolve, so the request carries a fully valid user identity — and must
    still be refused, because the taxonomy is shared state no user owns."""
    resp = _call(client, method, path, body, headers={"Authorization": "Bearer irrelevant"})
    assert resp.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ROUTES)
def test_write_with_key_succeeds(client: TestClient, method: str, path: str, body) -> None:  # type: ignore[no-untyped-def]
    """The control against having *closed* the routes rather than moved
    them. Without this, "everything is 401" and "it is broken" are
    indistinguishable."""
    resp = _call(client, method, path, body, headers=KEY_HEADER)
    assert resp.status_code in (200, 201, 204), resp.text


@pytest.mark.parametrize("path", READ_ROUTES)
def test_reads_still_work_with_user_jwt(client: TestClient, path: str) -> None:
    """The non-goal, asserted. A read path that broke would show up here
    rather than in the browser suite."""
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ROUTES)
def test_old_public_path_no_longer_writes(client: TestClient, method: str, path: str, body) -> None:  # type: ignore[no-untyped-def]
    """The write must be *gone* from the public prefix, not shadowed. 405
    is the expected answer: the public routers still exist for reads, so
    FastAPI reports Method Not Allowed rather than 404."""
    public_path = path.replace("/api/v1/internal/", "/api/v1/")
    resp = _call(client, method, public_path, body, headers=KEY_HEADER)
    assert resp.status_code in (404, 405), f"{method.upper()} {public_path} -> {resp.status_code}"


class TestUnconfiguredKey:
    def test_unset_key_is_503_not_open(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fail closed (P1-15's decision, inherited): an unset key must not
        mean "no auth required" on the taxonomy either."""
        monkeypatch.setattr(internal_auth.settings, "INTERNAL_API_KEY", None)
        app.dependency_overrides[get_category_service] = lambda: _StubCategoryService()
        try:
            resp = TestClient(app).put(
                "/api/v1/internal/categories/1",
                json={"name": "Omdoebt"},
                headers=KEY_HEADER,
            )
            assert resp.status_code == 503
        finally:
            app.dependency_overrides.clear()
