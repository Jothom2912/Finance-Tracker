"""Unit tests for Settings — verifies fail-fast on missing JWT_SECRET."""

from __future__ import annotations

import pytest
from app.config import Settings
from pydantic import ValidationError


def test_missing_jwt_secret_fails_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None)


def test_jwt_secret_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "some-secret")
    assert Settings(_env_file=None).JWT_SECRET == "some-secret"
