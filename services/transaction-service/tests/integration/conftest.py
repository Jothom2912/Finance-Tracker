"""Integration test conftest: set dummy env vars before app.config imports."""

import os

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost:5434/dummy")
os.environ.setdefault("JWT_SECRET", "test-secret")
