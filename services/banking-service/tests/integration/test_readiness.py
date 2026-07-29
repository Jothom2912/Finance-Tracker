"""
P2-42b — the two levels of ``GET /ready``.

The load-bearing test here is ``test_missing_pem_is_degraded_not_unavailable``.
Enable Banking is an *optional* integration (P2-42a): a deploy without a usable
PEM is unavailable-but-correct, so a broken PEM must not be able to take the pod
out of service.  That is a decision, not an implementation detail, and without a
test it is one refactor away from silently becoming a 503 — which would keep a
stack that does not use bank sync from ever coming up.

``/health`` is asserted to stay 200 in the same broken-PEM state.  It is liveness:
a live process with a broken optional dependency is exactly what it should report.
That assertion is the negative control from the plan, in test form.
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("ENABLE_BANKING_APP_ID", "test-app")
os.environ.setdefault("ENABLE_BANKING_KEY_PATH", "dummy.pem")
os.environ.setdefault("ENABLE_BANKING_REDIRECT_URI", "http://localhost/callback")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")

from contextlib import contextmanager
from typing import Iterator

import pytest
from app.config import settings
from app.database import get_db
from app.main import app
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


class FakeSession:
    """Stands in for AsyncSession; ``SELECT 1`` is the only call /ready makes."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    async def execute(self, _statement: object) -> None:
        if self._error is not None:
            raise self._error


@pytest.fixture
def pem_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Real RSA key: the client smoke-signs an RS256 JWT in its constructor."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path = tmp_path_factory.mktemp("keys") / "eb.pem"
    path.write_bytes(pem)
    return str(path)


@contextmanager
def readiness_env(
    *,
    key_path: str,
    app_id: str = "test-app",
    db_error: Exception | None = None,
) -> Iterator[None]:
    """
    Pin both dependencies for one request.

    The banking client is a process-wide singleton, so it is reset on both
    entry and exit: a cached client from another test would make a broken-PEM
    case pass for the wrong reason, and a client cached *here* would leak a
    broken one into the next test.
    """
    import app.dependencies as deps

    original = (settings.ENABLE_BANKING_KEY_PATH, settings.ENABLE_BANKING_APP_ID, deps._banking_client)
    settings.ENABLE_BANKING_KEY_PATH = key_path
    settings.ENABLE_BANKING_APP_ID = app_id
    deps._banking_client = None
    app.dependency_overrides[get_db] = lambda: FakeSession(db_error)
    try:
        yield
    finally:
        settings.ENABLE_BANKING_KEY_PATH, settings.ENABLE_BANKING_APP_ID, deps._banking_client = original
        app.dependency_overrides.clear()


def test_all_dependencies_ok_is_ready(pem_path: str) -> None:
    with readiness_env(key_path=pem_path), TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"]["database"]["ok"] is True
    assert body["dependencies"]["enable_banking"]["ok"] is True


def test_missing_pem_is_degraded_not_unavailable() -> None:
    """The decision from P2-42a, locked down: optional dependency ⇒ 200, never 503."""
    with readiness_env(key_path="/nonexistent/enablebanking.pem"), TestClient(app) as client:
        response = client.get("/ready")
        health = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["enable_banking"]["ok"] is False
    assert body["dependencies"]["database"]["ok"] is True

    # Negative control: the old probe is blind to this, and should stay blind.
    # /health is liveness — the process is fine.
    assert health.status_code == 200


def test_empty_app_id_is_degraded(pem_path: str) -> None:
    """Second Enable Banking failure mode: config present, app_id blank."""
    with readiness_env(key_path=pem_path, app_id=""), TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_unreachable_database_is_unavailable(pem_path: str) -> None:
    """Required dependency ⇒ 503, so k8s can pull the pod out of service."""
    db_error = OperationalError("SELECT 1", {}, Exception("connection refused"))
    with readiness_env(key_path=pem_path, db_error=db_error), TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["dependencies"]["database"]["ok"] is False
