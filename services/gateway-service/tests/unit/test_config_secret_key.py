from __future__ import annotations

import importlib
import os

import pytest


def test_missing_secret_key_fails_at_import(monkeypatch) -> None:
    """An empty SECRET_KEY would make jwt.decode accept tokens signed
    with "" — the config module must refuse to load without it."""
    import app.config as config

    original = os.environ.get("SECRET_KEY", "test-secret-key")

    # Neutralize load_dotenv so a developer's .env can't re-populate
    # the variable during the reload.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        importlib.reload(config)

    # Restore a usable module state for the rest of the test session.
    monkeypatch.setenv("SECRET_KEY", original)
    importlib.reload(config)
    assert config.SECRET_KEY == original


def test_secret_key_loaded_from_environment() -> None:
    import app.config as config

    assert config.SECRET_KEY == os.environ["SECRET_KEY"]
