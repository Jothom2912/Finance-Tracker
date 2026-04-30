"""Unit test conftest: set dummy env vars so Settings() doesn't fail on import."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5434/transactions")
os.environ.setdefault("JWT_SECRET", "test-secret")
