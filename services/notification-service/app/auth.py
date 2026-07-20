"""JWT validation for notification-service.

Tokens are issued by user-service; this service only validates them with the
shared platform secret via the finans-tracker-auth package (P2-02).
"""

from __future__ import annotations

from auth.fastapi import make_current_user_dependency

from app.config import settings

get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
