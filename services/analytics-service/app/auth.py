from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import Settings, settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


def make_service_auth_header(user_id: int, config: Settings | None = None) -> dict[str, str]:
    """Kortlivet service-JWT til backfill-kald mod kildeservices
    (budget-service-mønster)."""
    config = config or settings
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id_str = payload.get("sub") or str(payload.get("user_id", ""))
        if not user_id_str:
            raise credentials_exception
        return int(user_id_str)
    except (jwt.PyJWTError, KeyError, ValueError) as err:
        raise credentials_exception from err
