from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from auth.jwt import InvalidTokenError, decode_token
from jose import jwt as jose_jwt

SECRET = "test-secret"
OTHER_SECRET = "a-different-secret"


def _make_token(claims: dict, secret: str = SECRET, algorithm: str = "HS256") -> str:
    return jose_jwt.encode(claims, secret, algorithm=algorithm)


class TestDecodeTokenValid:
    def test_decodes_sub_claim_to_user_id(self) -> None:
        token = _make_token({"sub": "42"})

        claims = decode_token(token, SECRET)

        assert claims["user_id"] == 42

    def test_decodes_user_id_claim(self) -> None:
        token = _make_token({"user_id": 7})

        claims = decode_token(token, SECRET)

        assert claims["user_id"] == 7

    def test_user_id_claim_takes_priority_over_sub(self) -> None:
        token = _make_token({"user_id": 7, "sub": "99"})

        claims = decode_token(token, SECRET)

        assert claims["user_id"] == 7

    def test_preserves_other_claims(self) -> None:
        token = _make_token({"sub": "1", "username": "alice", "email": "a@b.com"})

        claims = decode_token(token, SECRET)

        assert claims["username"] == "alice"
        assert claims["email"] == "a@b.com"

    def test_valid_unexpired_token_with_exp(self) -> None:
        exp = datetime.now(timezone.utc) + timedelta(minutes=5)
        token = _make_token({"sub": "1", "exp": exp})

        claims = decode_token(token, SECRET)

        assert claims["user_id"] == 1


class TestDecodeTokenExpired:
    def test_expired_token_raises(self) -> None:
        exp = datetime.now(timezone.utc) - timedelta(minutes=5)
        token = _make_token({"sub": "1", "exp": exp})

        with pytest.raises(InvalidTokenError):
            decode_token(token, SECRET)

    def test_token_without_exp_is_accepted_by_default(self) -> None:
        """require_exp defaults to False, preserving current service behavior."""
        token = _make_token({"sub": "1"})

        claims = decode_token(token, SECRET)

        assert claims["user_id"] == 1

    def test_token_without_exp_rejected_when_require_exp_true(self) -> None:
        token = _make_token({"sub": "1"})

        with pytest.raises(InvalidTokenError):
            decode_token(token, SECRET, require_exp=True)

    def test_token_with_exp_accepted_when_require_exp_true(self) -> None:
        exp = datetime.now(timezone.utc) + timedelta(minutes=5)
        token = _make_token({"sub": "1", "exp": exp})

        claims = decode_token(token, SECRET, require_exp=True)

        assert claims["user_id"] == 1


class TestDecodeTokenWrongSecret:
    def test_wrong_secret_raises(self) -> None:
        token = _make_token({"sub": "1"}, secret=SECRET)

        with pytest.raises(InvalidTokenError):
            decode_token(token, OTHER_SECRET)


class TestDecodeTokenSubVsUserId:
    def test_missing_both_claims_raises(self) -> None:
        token = _make_token({"username": "alice"})

        with pytest.raises(InvalidTokenError):
            decode_token(token, SECRET)

    def test_non_numeric_sub_raises_clean_error(self) -> None:
        token = _make_token({"sub": "not-a-number"})

        with pytest.raises(InvalidTokenError) as exc_info:
            decode_token(token, SECRET)

        assert "not-a-number" in str(exc_info.value)

    def test_non_numeric_user_id_raises_clean_error(self) -> None:
        token = _make_token({"user_id": "abc"})

        with pytest.raises(InvalidTokenError):
            decode_token(token, SECRET)

    def test_null_sub_raises(self) -> None:
        token = _make_token({"sub": None})

        with pytest.raises(InvalidTokenError):
            decode_token(token, SECRET)


class TestDecodeTokenMalformed:
    def test_garbage_token_raises(self) -> None:
        with pytest.raises(InvalidTokenError):
            decode_token("not-a-jwt-at-all", SECRET)

    def test_wrong_algorithm_rejected(self) -> None:
        token = _make_token({"sub": "1"}, algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            decode_token(token, SECRET, algorithms=["HS512"])
