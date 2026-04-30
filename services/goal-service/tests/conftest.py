from __future__ import annotations

import os
import sys
from pathlib import Path

# Make service code and shared contracts importable in tests without manual env setup.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
SHARED_CONTRACTS = SERVICE_ROOT.parent / "shared" / "contracts"

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

for path in (SERVICE_ROOT, SHARED_CONTRACTS):
    path_str = str(path)
    if path.exists() and path_str not in sys.path:
        sys.path.insert(0, path_str)
