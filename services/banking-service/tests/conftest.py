"""Test bootstrap for banking-service.

banking-service had no conftest, and ``app.config.Settings`` requires
``DATABASE_URL`` (no default, and there is no committed ``.env``).  Importing
anything under ``app`` therefore raised ``ValidationError`` at *collection*
time unless the caller happened to export the right variables by hand.

That made the CI job unrunnable: the workflow sets ``JWT_SECRET`` but not
``DATABASE_URL``, so ``pytest tests`` could never collect.  The failure was
masked until 2026-07-25 because the ``ruff format --check`` step failed
earlier in the same job and aborted it (commit d5630a6e fixed the formatting
and thereby uncovered this).

Same shape as the other seven services' conftests: set the env and put the
service root plus the shared packages on ``sys.path`` so a bare
``pytest tests`` works with no incantation.  banking-service has no
``pyproject.toml`` (requirements.txt only), so the path setup cannot come
from a package install.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SHARED = SERVICE_ROOT.parent / "shared"

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

for path in (SERVICE_ROOT, SHARED / "contracts", SHARED / "messaging", SHARED / "auth"):
    path_str = str(path)
    if path.exists() and path_str not in sys.path:
        sys.path.insert(0, path_str)
