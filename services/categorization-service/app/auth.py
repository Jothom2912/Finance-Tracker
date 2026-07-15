"""JWT validation for categorization-service — token consumer, not issuer.

Decoding is delegated to the shared finans-tracker-auth package (P2-02).
Note two deliberate behavior changes from the old HTTPBearer-based local
implementation: a missing Authorization header now yields 401 (was 403 via
HTTPBearer's auto_error), and tokens carrying only a ``user_id`` claim (no
``sub``) are now accepted like in every other service.
"""

from __future__ import annotations

from auth.fastapi import make_current_user_dependency

from app.config import settings

get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
