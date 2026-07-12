from __future__ import annotations

import app.adapters.inbound.saga_api as saga_api
import app.adapters.outbound.saga_client as sc
from app import auth
from app.adapters.outbound.saga_client import SagaServiceClient
from app.main import app
from fastapi.testclient import TestClient
from jose import jwt


class _FakeResponse:
    def __init__(self) -> None:
        self._payload = {"saga_id": "s-1", "status": "completed", "context": {"user_id": 42}}

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _FakeHttpxClient:
    def __init__(self, calls: list[dict]) -> None:
        self._calls = calls

    def __enter__(self) -> _FakeHttpxClient:
        return self

    def __exit__(self, *args) -> bool:
        return False

    def get(self, url: str, headers: dict | None = None) -> _FakeResponse:
        self._calls.append({"url": url, "headers": headers})
        return _FakeResponse()


def test_saga_client_forwards_auth_header(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(sc.httpx, "Client", lambda timeout=None: _FakeHttpxClient(calls))

    SagaServiceClient("Bearer abc").get_saga_status("s-1")

    assert calls[0]["headers"] == {"Authorization": "Bearer abc"}


def test_saga_client_sends_no_auth_header_when_empty(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(sc.httpx, "Client", lambda timeout=None: _FakeHttpxClient(calls))

    SagaServiceClient("").get_saga_status("s-1")

    assert calls[0]["headers"] == {}


def test_saga_route_passes_incoming_authorization_to_client(monkeypatch) -> None:
    captured: dict = {}

    class FakeSagaServiceClient:
        def __init__(self, auth_header: str) -> None:
            captured["auth_header"] = auth_header

        def get_saga_status(self, saga_id: str) -> dict:
            return {"saga_id": saga_id, "status": "completed", "context": {"user_id": 42}}

    monkeypatch.setattr(saga_api, "SagaServiceClient", FakeSagaServiceClient)

    token = jwt.encode({"user_id": 42}, auth.SECRET_KEY, algorithm=auth.JWT_ALGORITHM)
    client = TestClient(app)
    resp = client.get("/api/v1/sagas/s-1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert captured["auth_header"] == f"Bearer {token}"


def test_saga_route_still_enforces_ownership(monkeypatch) -> None:
    class FakeSagaServiceClient:
        def __init__(self, auth_header: str) -> None:
            pass

        def get_saga_status(self, saga_id: str) -> dict:
            return {"saga_id": saga_id, "status": "completed", "context": {"user_id": 999}}

    monkeypatch.setattr(saga_api, "SagaServiceClient", FakeSagaServiceClient)

    token = jwt.encode({"user_id": 42}, auth.SECRET_KEY, algorithm=auth.JWT_ALGORITHM)
    client = TestClient(app)
    resp = client.get("/api/v1/sagas/s-1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
