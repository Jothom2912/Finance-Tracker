"""Budget-service auth: shared JWT validation + local S2S token minting.

Validation of inbound tokens is delegated to the shared finans-tracker-auth
package (P2-02). ``make_service_auth_header`` stays local on purpose: it
*mints* tokens for service-to-service calls, which the shared package
deliberately does not do — and the forged-user-token approach itself is
slated for replacement by real S2S credentials (P3-02).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from auth.fastapi import make_current_user_dependency
from jose import jwt

from app.config import settings


def make_service_auth_header(user_id: int = 0) -> dict[str, str]:
    """Generate a short-lived JWT for service-to-service HTTP calls."""
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
