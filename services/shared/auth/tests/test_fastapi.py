from __future__ import annotations

from datetime import datetime, timedelta, timezone

from auth.fastapi import make_current_user_dependency
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

SECRET = "test-secret"


def _make_token(claims: dict, secret: str = SECRET) -> str:
    return jose_jwt.encode(claims, secret, algorithm="HS256")


def _build_app(**dependency_kwargs) -> FastAPI:
    app = FastAPI()
    get_current_user_id = make_current_user_dependency(lambda: SECRET, **dependency_kwargs)

    @app.get("/whoami")
    def whoami(user_id: int = Depends(get_current_user_id)):
        return {"user_id": user_id}

    return app


class TestDependencyHappyPath:
    def test_valid_bearer_token_returns_user_id(self) -> None:
        client = TestClient(_build_app())
        token = _make_token({"sub": "42"})

        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json() == {"user_id": 42}

    def test_valid_user_id_claim_returns_user_id(self) -> None:
        client = TestClient(_build_app())
        token = _make_token({"user_id": 7})

        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json() == {"user_id": 7}


class TestDependencyMissingHeader:
    def test_missing_authorization_header_is_401(self) -> None:
        client = TestClient(_build_app())

        response = client.get("/whoami")

        assert response.status_code == 401
        assert response.json()["detail"] == "Missing authentication token"
        assert response.headers["www-authenticate"] == "Bearer"


class TestDependencyMalformedHeader:
    def test_missing_bearer_prefix_is_401(self) -> None:
        client = TestClient(_build_app())
        token = _make_token({"sub": "1"})

        response = client.get("/whoami", headers={"Authorization": token})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication format. Use: Bearer <token>"
        assert response.headers["www-authenticate"] == "Bearer"

    def test_wrong_scheme_is_401(self) -> None:
        client = TestClient(_build_app())
        token = _make_token({"sub": "1"})

        response = client.get("/whoami", headers={"Authorization": f"Basic {token}"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication format. Use: Bearer <token>"

    def test_too_many_parts_is_401(self) -> None:
        client = TestClient(_build_app())

        response = client.get("/whoami", headers={"Authorization": "Bearer abc def"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication format. Use: Bearer <token>"


class TestDependencyInvalidToken:
    def test_expired_token_is_401(self) -> None:
        client = TestClient(_build_app())
        exp = datetime.now(timezone.utc) - timedelta(minutes=5)
        token = _make_token({"sub": "1", "exp": exp})

        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"
        assert response.headers["www-authenticate"] == "Bearer"

    def test_wrong_secret_is_401(self) -> None:
        client = TestClient(_build_app())
        token = _make_token({"sub": "1"}, secret="wrong-secret")

        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"

    def test_garbage_token_is_401(self) -> None:
        client = TestClient(_build_app())

        response = client.get("/whoami", headers={"Authorization": "Bearer not-a-jwt"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"

    def test_non_numeric_sub_is_401(self) -> None:
        client = TestClient(_build_app())
        token = _make_token({"sub": "not-a-number"})

        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"


class TestDependencyRequireExpOptIn:
    def test_require_exp_true_rejects_token_without_exp(self) -> None:
        client = TestClient(_build_app(require_exp=True))
        token = _make_token({"sub": "1"})

        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401

    def test_require_exp_true_accepts_token_with_exp(self) -> None:
        client = TestClient(_build_app(require_exp=True))
        exp = datetime.now(timezone.utc) + timedelta(minutes=5)
        token = _make_token({"sub": "1", "exp": exp})

        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
