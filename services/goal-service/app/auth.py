"""JWT validation for goal-service.

Tokens are issued by user-service. Goal-service only validates them with the
shared JWT secret used by the rest of the platform.
"""

from __future__ import annotations

from app.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
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
