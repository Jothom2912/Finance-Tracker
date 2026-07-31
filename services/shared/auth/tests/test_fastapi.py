from __future__ import annotations

import logging
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


class TestDependencyLogging:
    """P3-59: den udekodbare token er den ENE 401-gren der logger.

    De to andre grene er entydige ud fra statuskoden alene, og admissionsreglen afviser
    dem — de negative tests nedenfor er derfor selve indholdet af beslutningen, ikke
    dækningspynt.  Uden dem kan en senere "log alle 401'er" glide ind og gøre linjen til
    en anden access-log.
    """

    def test_undecodable_token_logs_warning_naming_the_reason(self, caplog) -> None:
        client = TestClient(_build_app())
        token = _make_token({"sub": "1"}, secret="wrong-secret")

        with caplog.at_level(logging.WARNING, logger="auth.fastapi"):
            client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        records = [r for r in caplog.records if r.name == "auth.fastapi"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        # Den diskriminerende værdi: linjen skal sige HVORFOR, ikke bare "afvist".
        # ``Signature verification failed`` er joses besked for forkert hemmelighed.
        assert "Signature verification failed" in records[0].getMessage()

    def test_expired_token_reason_differs_from_bad_signature(self, caplog) -> None:
        """Hele pointen er at skelne de tre årsager, så to af dem skal give to beskeder."""
        client = TestClient(_build_app())
        exp = datetime.now(timezone.utc) - timedelta(minutes=5)
        token = _make_token({"sub": "1", "exp": exp})

        with caplog.at_level(logging.WARNING, logger="auth.fastapi"):
            client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        message = caplog.records[-1].getMessage()
        assert "expired" in message.lower()
        assert "Signature verification failed" not in message

    def test_missing_identity_claim_is_logged(self, caplog) -> None:
        client = TestClient(_build_app())
        token = _make_token({"foo": "bar"})

        with caplog.at_level(logging.WARNING, logger="auth.fastapi"):
            client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        assert "missing a 'user_id' or 'sub' claim" in caplog.records[-1].getMessage()

    def test_log_line_never_contains_the_token(self, caplog) -> None:
        """Et afvist token er stadig et gyldigt credential for den der kan bruge det."""
        client = TestClient(_build_app())
        token = _make_token({"sub": "1"}, secret="wrong-secret")

        with caplog.at_level(logging.WARNING, logger="auth.fastapi"):
            client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

        for record in caplog.records:
            assert token not in record.getMessage()

    def test_missing_header_does_not_log(self, caplog) -> None:
        client = TestClient(_build_app())

        with caplog.at_level(logging.DEBUG, logger="auth.fastapi"):
            response = client.get("/whoami")

        assert response.status_code == 401
        assert [r for r in caplog.records if r.name == "auth.fastapi"] == []

    def test_malformed_bearer_format_does_not_log(self, caplog) -> None:
        client = TestClient(_build_app())

        with caplog.at_level(logging.DEBUG, logger="auth.fastapi"):
            response = client.get("/whoami", headers={"Authorization": "Basic abc"})

        assert response.status_code == 401
        assert [r for r in caplog.records if r.name == "auth.fastapi"] == []

    def test_valid_token_does_not_log(self, caplog) -> None:
        client = TestClient(_build_app())

        with caplog.at_level(logging.DEBUG, logger="auth.fastapi"):
            response = client.get("/whoami", headers={"Authorization": f"Bearer {_make_token({'sub': '5'})}"})

        assert response.status_code == 200
        assert [r for r in caplog.records if r.name == "auth.fastapi"] == []


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
