from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure tests can import both goal-service app package and shared contracts
SERVICE_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_ROOT = SERVICE_ROOT.parent / "shared" / "contracts"

# Ensure required settings are present in test environment.
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

for path in (SERVICE_ROOT, CONTRACTS_ROOT):
    path_str = str(path)
    if path.exists() and path_str not in sys.path:
        sys.path.insert(0, path_str)
