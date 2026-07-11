from __future__ import annotations

import os

# The gateway fails fast when SECRET_KEY is missing (see app/config.py).
# Provide a deterministic test secret before any app module is imported.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
