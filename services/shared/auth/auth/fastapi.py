"""FastAPI dependency factory for extracting the current user id from a
bearer token, mirroring the status/detail semantics shared by
banking-service, saga-service and account-service today.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from fastapi import Header, HTTPException, status

from .jwt import DEFAULT_ALGORITHMS, InvalidTokenError, decode_token

SecretProvider = Callable[[], str]
"""A zero-argument callable returning the current shared JWT secret.

Provided as a callable (rather than a plain string) so each service can
keep resolving the secret from its own ``Settings`` object, including
services that reload configuration at runtime or in tests.
"""

CurrentUserDependency = Callable[..., int]


def make_current_user_dependency(
    secret_provider: SecretProvider,
    algorithms: Sequence[str] = DEFAULT_ALGORITHMS,
    require_exp: bool = False,
) -> CurrentUserDependency:
    """Build a FastAPI dependency that resolves the authenticated user id.

    Usage::

        from auth.fastapi import make_current_user_dependency
        from app.config import settings

        get_current_user_id = make_current_user_dependency(lambda: settings.JWT_SECRET)

        @router.get("/me")
        def me(user_id: int = Depends(get_current_user_id)):
            ...

    The returned dependency reproduces the three-message 401 flow used by
    banking-service/saga-service/account-service today:

    - Missing ``Authorization`` header -> 401 "Missing authentication token"
    - Header present but not ``Bearer <token>`` -> 401 "Invalid authentication
      format. Use: Bearer <token>"
    - Header well-formed but the token fails to decode/validate -> 401
      "Invalid or expired authentication token"

    All three responses carry a ``WWW-Authenticate: Bearer`` header.
    """

    def get_current_user_id(
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ) -> int:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication format. Use: Bearer <token>",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            claims = decode_token(
                parts[1],
                secret_provider(),
                algorithms=algorithms,
                require_exp=require_exp,
            )
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return claims["user_id"]

    return get_current_user_id
