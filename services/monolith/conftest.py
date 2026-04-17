"""Root conftest — runs before any test module is imported.

Purpose: set default environment variables that must be present when
``backend.*`` modules import.  Individual tests can still override via
``monkeypatch`` or their own fixtures.

Speedups applied here:
- ``BCRYPT_ROUNDS=4`` drops password hashing from ~1s to ~1ms.
- ``SKIP_DB_BOOTSTRAP=1`` bypasses the MySQL connection probe in the
  FastAPI lifespan, which otherwise blocks each ``TestClient(app)``
  context for several seconds while it times out against a database
  that isn't running.
"""

from __future__ import annotations

import os

os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("SKIP_DB_BOOTSTRAP", "1")
