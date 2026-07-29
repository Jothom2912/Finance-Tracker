"""S2S guard shared by the service's internal routers.

Lives here rather than in one of the routers because two routers need it
(`categorize_router` since P1-15, the taxonomy write router since P2-28)
and a second copy is precisely P2-36's failure class.
"""

from __future__ import annotations

from hmac import compare_digest

from fastapi import Header, HTTPException, status

from app.config import settings


def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> None:
    """S2S guard — same shape as user-service's internal lookup.

    ``compare_digest`` rather than ``!=`` so a wrong key costs the same
    time regardless of how many leading bytes matched.

    Fails closed: an unconfigured key answers 503, never "no auth
    required" (P1-15).
    """
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API is not configured",
        )
    if not x_internal_api_key or not compare_digest(x_internal_api_key, settings.INTERNAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
