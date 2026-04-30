"""Root conftest: disable Testcontainers Ryuk on Windows (Docker Desktop compatibility)."""

import os

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
