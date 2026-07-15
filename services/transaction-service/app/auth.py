"""JWT token validation only — transaction-service is a token consumer, not an issuer.

Tokens are created by user-service. All services share the same JWT_SECRET
so tokens are valid across the platform. Decoding is delegated to the shared
finans-tracker-auth package (P2-02).
"""

from __future__ import annotations

from auth.fastapi import make_current_user_dependency

from app.config import settings

get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
