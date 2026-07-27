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

P3-23 removed the ``sys.path`` half of this file.  It used to insert the
service root and ``shared/{contracts,messaging,auth}`` because there was no
``pyproject.toml`` to install from — that premise is gone: the three shared
packages are declared path-dependencies and ``uv sync`` puts them in the venv.
Keeping the insertion would import them from the source tree while mypy reads
the installed copy, which is two sources of truth for one package.  The env
defaults stay; they are what makes collection possible at all.
"""

from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
# Required since P1-15/D1 removed the dev-string default from config.py.
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-api-key")
