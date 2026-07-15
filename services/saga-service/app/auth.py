"""JWT validation for saga-service — token consumer, not issuer (P1-04).

Decoding is delegated to the shared finans-tracker-auth package (P2-02);
the shared dependency reproduces this service's exact three-message 401 flow.
"""

from __future__ import annotations

from auth.fastapi import make_current_user_dependency

from app.config import settings

# Fail fast at startup rather than 401'ing every request (P1-06).
if not settings.JWT_SECRET:
    raise ValueError("JWT_SECRET must be set in environment variables.")

get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
