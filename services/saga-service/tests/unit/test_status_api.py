from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from app.adapters.outbound.postgres_saga_repository import PostgresSagaRepository
from app.config import settings
from app.domain.entities import SagaInstance, SagaStatus, SagaStep, StepStatus
from app.main import app
from fastapi.testclient import TestClient
from jose import jwt

SAGA_ID = "saga-123"
OWNER_USER_ID = 1
OTHER_USER_ID = 2


def make_auth_header(user_id: int = OWNER_USER_ID) -> dict[str, str]:
    token = jwt.encode(
        {
            "user_id": user_id,
            "username": "testuser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_saga() -> SagaInstance:
    return SagaInstance(
        id=SAGA_ID,
        saga_type="bank_sync",
        correlation_id=SAGA_ID,
        current_step=2,
        status=SagaStatus.COMPLETED,
        context={
            "user_id": OWNER_USER_ID,
            "connection_id": "conn-1",
            "fetched_items": [{"amount": "10.00", "description": "secret bank tx"}],
            "imported_ids": [501, 502],
            "total_fetched": 2,
            "new_imported": 2,
            "duplicates_skipped": 0,
        },
        steps=[
            SagaStep(index=0, name="fetch_transactions", status=StepStatus.SUCCEEDED),
            SagaStep(index=1, name="import_transactions", status=StepStatus.SUCCEEDED),
            SagaStep(index=2, name="mark_sync_complete", status=StepStatus.SUCCEEDED),
        ],
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    saga = _make_saga()

    async def fake_get_by_id(self: PostgresSagaRepository, saga_id: str) -> SagaInstance | None:
        return saga if saga_id == SAGA_ID else None

    async def fake_get_by_correlation_id(self: PostgresSagaRepository, correlation_id: str) -> SagaInstance | None:
        return None

    monkeypatch.setattr(PostgresSagaRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresSagaRepository, "get_by_correlation_id", fake_get_by_correlation_id)
    return TestClient(app)


def test_get_saga_status_without_token_returns_401(client: TestClient) -> None:
    resp = client.get(f"/api/v1/sagas/{SAGA_ID}")
    assert resp.status_code == 401


def test_get_saga_status_with_invalid_token_returns_401(client: TestClient) -> None:
    resp = client.get(f"/api/v1/sagas/{SAGA_ID}", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_get_saga_status_with_other_users_token_returns_403(client: TestClient) -> None:
    resp = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=make_auth_header(OTHER_USER_ID))
    assert resp.status_code == 403


def test_get_saga_status_unknown_saga_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/sagas/unknown-saga", headers=make_auth_header())
    assert resp.status_code == 404


def test_get_saga_status_strips_fetched_items_but_keeps_user_id(client: TestClient) -> None:
    resp = client.get(f"/api/v1/sagas/{SAGA_ID}", headers=make_auth_header())

    assert resp.status_code == 200
    body = resp.json()
    assert body["saga_id"] == SAGA_ID
    assert body["status"] == "completed"
    assert body["current_step_name"] == "mark_sync_complete"

    context = body["context"]
    assert "fetched_items" not in context
    assert "items" not in context
    # Fields consumed by the gateway ownership check and the frontend result message.
    assert context["user_id"] == OWNER_USER_ID
    assert context["total_fetched"] == 2
    assert context["new_imported"] == 2
    assert context["duplicates_skipped"] == 0


@pytest.mark.parametrize(
    ("context", "case"),
    [
        ({}, "user_id missing entirely"),
        ({"user_id": None}, "user_id present but null"),
        ({"user_id": "not-a-number"}, "user_id not coercible to int"),
        ({"user_id": ["1"]}, "user_id is a list"),
    ],
)
def test_get_saga_status_denies_when_context_owner_is_unusable(
    monkeypatch: pytest.MonkeyPatch,
    context: dict[str, object],
    case: str,
) -> None:
    """A saga whose context carries no usable owner is 403, never 500.

    The ownership check coerces ``context["user_id"]`` to int, and P2-31's gate
    flagged that it fed ``int()`` a possibly-None value. Rewriting it to spell the
    None case out is only safe if every unusable shape still denies access rather
    than raising — so the shapes are pinned here, not argued about.
    """
    saga = _make_saga()
    saga.context = context

    async def fake_get_by_id(self: PostgresSagaRepository, saga_id: str) -> SagaInstance | None:
        return saga if saga_id == SAGA_ID else None

    async def fake_get_by_correlation_id(self: PostgresSagaRepository, correlation_id: str) -> SagaInstance | None:
        return None

    monkeypatch.setattr(PostgresSagaRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresSagaRepository, "get_by_correlation_id", fake_get_by_correlation_id)

    resp = TestClient(app).get(f"/api/v1/sagas/{SAGA_ID}", headers=make_auth_header())

    assert resp.status_code == 403, case
