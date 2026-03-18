"""Tests for JWT cross-service compatibility.

Verifies that the monolith's auth module produces tokens with the
``sub`` claim and can decode tokens issued in both the monolith format
(``user_id``) and the microservice format (``sub``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.auth import (
    ALGORITHM,
    create_access_token,
    decode_token,
)
from backend.config import SECRET_KEY
from jose import jwt


class TestCreateTokenFormat:
    def test_token_contains_sub_field(self) -> None:
        token = create_access_token(user_id=42, username="alice", email="alice@example.com")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "42"

    def test_token_still_contains_legacy_fields(self) -> None:
        token = create_access_token(user_id=7, username="bob", email="bob@example.com")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["user_id"] == 7
        assert payload["username"] == "bob"
        assert payload["email"] == "bob@example.com"
        assert "exp" in payload


class TestDecodeTokenCrossFormat:
    def test_decode_monolith_format(self) -> None:
        """Token with user_id/username/email (monolith format)."""
        token = jwt.encode(
            {
                "user_id": 10,
                "username": "carol",
                "email": "carol@example.com",
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        data = decode_token(token)

        assert data is not None
        assert data.user_id == 10
        assert data.username == "carol"
        assert data.email == "carol@example.com"

    def test_decode_microservice_format(self) -> None:
        """Token with only sub (user-service / transaction-service format)."""
        token = jwt.encode(
            {
                "sub": "25",
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        data = decode_token(token)

        assert data is not None
        assert data.user_id == 25
        assert data.username is None
        assert data.email is None

    def test_decode_combined_format(self) -> None:
        """Token with both sub and user_id prefers user_id."""
        token = create_access_token(user_id=99, username="eve", email="eve@example.com")

        data = decode_token(token)

        assert data is not None
        assert data.user_id == 99

    def test_decode_no_user_id_or_sub_returns_none(self) -> None:
        token = jwt.encode(
            {"exp": datetime.utcnow() + timedelta(hours=1)},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        assert decode_token(token) is None

    def test_decode_invalid_token_returns_none(self) -> None:
        assert decode_token("garbage.token.here") is None
