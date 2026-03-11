"""JWT token validation only — transaction-service is a token consumer, not an issuer.

Tokens are created by user-service. All services share the same JWT_SECRET
so tokens are valid across the platform.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="http://localhost:8001/api/v1/users/login",
)


async def get_current_user_id(
    token: str = Depends(oauth2_scheme),
) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id_str = payload.get("sub") or str(payload.get("user_id", ""))
        if not user_id_str:
            raise credentials_exception
        return int(user_id_str)
    except (JWTError, KeyError, ValueError) as err:
        raise credentials_exception from err
