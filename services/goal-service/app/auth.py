"""JWT validation for goal-service.

Tokens are issued by user-service. Goal-service only validates them with the
shared JWT secret used by the rest of the platform. Decoding is delegated to
the shared finans-tracker-auth package (P2-02).
"""

from __future__ import annotations

from app.config import settings
from auth.fastapi import make_current_user_dependency

get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
