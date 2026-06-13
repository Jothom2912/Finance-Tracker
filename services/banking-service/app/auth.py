from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

if not settings.JWT_SECRET:
    raise ValueError("JWT_SECRET must be set in environment variables.")


class TokenData(BaseModel):
    user_id: int
    username: Optional[str] = None
    email: Optional[str] = None


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            sub = payload.get("sub")
            if sub is None:
                return None
            user_id = int(sub)
        return TokenData(
            user_id=user_id,
            username=payload.get("username"),
            email=payload.get("email"),
        )
    except (JWTError, ValueError, TypeError):
        return None


def get_current_user_id(authorization: Optional[str] = Header(None, alias="Authorization")) -> int:
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
    token_data = decode_token(parts[1])
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data.user_id
