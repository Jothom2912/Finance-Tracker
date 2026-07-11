from __future__ import annotations

import os

# Must be set before any app module is imported (app.config requires it).
os.environ.setdefault("JWT_SECRET", "test-secret-key")
