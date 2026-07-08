"""Root conftest.

Provide dummy defaults for required settings so test modules that import
application code at module level don't fail at ``Settings()`` construction.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret")
