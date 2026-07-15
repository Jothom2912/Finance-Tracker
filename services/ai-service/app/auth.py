"""JWT token validation — ai-service is a token consumer, not an issuer.

Tokens are created by user-service. All services share the same JWT_SECRET.
Decoding is delegated to the shared finans-tracker-auth package (P2-02).

Raw-token forwarding to analytics-/transaction-service (AI-19) is unaffected:
the inbound adapters read the Authorization header directly off the Request
and never depend on this module for credential extraction.
"""

from __future__ import annotations

from auth.fastapi import make_current_user_dependency

from app.config import settings

get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
