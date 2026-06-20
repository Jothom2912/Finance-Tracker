"""Root conftest.

- Disable Testcontainers Ryuk on Windows (Docker Desktop compatibility).
- Provide dummy defaults for required settings so test modules that import
  the FastAPI app at module level (e.g. routing tests) don't fail at
  ``Settings()`` construction.  Tests needing a real DB (testcontainers)
  hard-set ``DATABASE_URL``, which overrides these defaults.
"""

import os

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "test-secret")
