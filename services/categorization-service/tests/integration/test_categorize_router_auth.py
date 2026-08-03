"""P1-15 — /api/v1/categorize is S2S-only.

The endpoint was reachable without credentials and took ``user_id`` from
the body, making the response's ``tier`` field an oracle over other
users' private F1-02 rules.

These tests exist because the service's own suite calls the
categorization service object directly and never the router — so the
dependency added in A2 would otherwise be entirely untested.

DB-free: ``build_categorization_service`` is monkeypatched and TestClient
is not used as a context manager, so startup warmup never hits the DB.
"""

from __future__ import annotations

import pytest
from app.adapters.inbound import categorize_api
from app.adapters.inbound.categorize_api import MAX_BATCH_ITEMS
from app.application.dto import CategorizeRequestDTO, CategorizeResponseDTO
from app.main import app
from fastapi.testclient import TestClient

KEY = "internal-key-for-tests"

BODY = {"description": "SHOP N PLAY", "amount": -249.0, "direction": "outgoing"}


class _StubService:
    async def categorize(self, _dto) -> CategorizeResponseDTO:  # type: ignore[no-untyped-def]
        return CategorizeResponseDTO(
            category_id=1,
            subcategory_id=5,
            tier="rule",
            confidence="high",
        )

    async def categorize_batch(self, dtos) -> list[CategorizeResponseDTO]:  # type: ignore[no-untyped-def]
        return [await self.categorize(dto) for dto in dtos]


@pytest.fixture()
def built_with() -> list[int | None]:
    """Records the ``user_id`` the router asks the factory to scope to."""
    return []


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, built_with: list[int | None]) -> TestClient:
    async def _build(user_id: int | None = None):  # type: ignore[no-untyped-def]
        built_with.append(user_id)
        return _StubService()

    monkeypatch.setattr(categorize_api, "build_categorization_service", _build)
    monkeypatch.setattr(categorize_api.settings, "INTERNAL_API_KEY", KEY)
    return TestClient(app)


class TestSingleEndpoint:
    def test_no_key_is_401(self, client: TestClient) -> None:
        response = client.post("/api/v1/categorize/", json=BODY)
        assert response.status_code == 401

    def test_wrong_key_is_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/",
            json=BODY,
            headers={"X-Internal-API-Key": "wrong"},
        )
        assert response.status_code == 401

    def test_correct_key_is_200(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/",
            json=BODY,
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 200
        assert response.json()["tier"] == "rule"

    def test_header_name_is_case_insensitive(self, client: TestClient) -> None:
        """goal-service sends the header lowercased; HTTP header names are
        case-insensitive and Starlette must treat them so."""
        response = client.post(
            "/api/v1/categorize/",
            json=BODY,
            headers={"x-internal-api-key": KEY},
        )
        assert response.status_code == 200


class TestBatchEndpoint:
    def test_no_key_is_401(self, client: TestClient) -> None:
        response = client.post("/api/v1/categorize/batch", json=[BODY])
        assert response.status_code == 401

    def test_correct_key_is_200(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/batch",
            json=[BODY],
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestBatchBounds:
    """A3 — the batch is bounded at the same 500 as
    BulkCreateTransactionDTO, its only real producer."""

    def test_at_the_ceiling_is_accepted(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/batch",
            json=[BODY] * MAX_BATCH_ITEMS,
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 200

    def test_over_the_ceiling_is_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/batch",
            json=[BODY] * (MAX_BATCH_ITEMS + 1),
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 422

    def test_empty_batch_is_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/batch",
            json=[],
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 422

    def test_oversized_batch_is_rejected_before_auth_is_moot(self, client: TestClient) -> None:
        """Auth still runs first — an unauthenticated oversized batch must
        not reveal which limit it tripped."""
        response = client.post(
            "/api/v1/categorize/batch",
            json=[BODY] * (MAX_BATCH_ITEMS + 1),
        )
        assert response.status_code == 401


class TestUserIdIsGone:
    """A3 — the field that made the endpoint an oracle is removed, not
    just fenced in. Pydantic ignores unknown keys by default, so the
    assertion is that it has no effect, not that it 422s."""

    def test_user_id_in_body_does_not_scope_the_engine(self, client: TestClient, built_with: list[int | None]) -> None:
        response = client.post(
            "/api/v1/categorize/",
            json={**BODY, "user_id": 1},
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 200
        assert built_with == [None]

    def test_batch_user_id_does_not_scope_the_engine(self, client: TestClient, built_with: list[int | None]) -> None:
        response = client.post(
            "/api/v1/categorize/batch",
            json=[{**BODY, "user_id": 1}, {**BODY, "user_id": 2}],
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 200
        assert built_with == [None]

    def test_dto_has_no_user_id_field(self) -> None:
        assert "user_id" not in CategorizeRequestDTO.model_fields


class TestUnconfiguredKey:
    def test_missing_config_is_503_not_open(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fail closed: an unset key must not mean "no auth required"."""
        monkeypatch.setattr(categorize_api.settings, "INTERNAL_API_KEY", None)
        response = TestClient(app).post(
            "/api/v1/categorize/",
            json=BODY,
            headers={"X-Internal-API-Key": KEY},
        )
        assert response.status_code == 503

    def test_missing_config_rejects_unauthenticated_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(categorize_api.settings, "INTERNAL_API_KEY", None)
        response = TestClient(app).post("/api/v1/categorize/", json=BODY)
        assert response.status_code == 503


class TestTaxonomyRoutesUnaffected:
    def test_categories_route_does_not_require_the_internal_key(self, client: TestClient) -> None:
        """The guard is scoped to categorize_router only — the frontend's
        /categories path must keep its JWT-based auth, not gain an S2S
        requirement it cannot satisfy."""
        response = client.get("/api/v1/categories/")
        assert response.status_code != 503
        assert response.json().get("detail") != "Invalid internal API key"
