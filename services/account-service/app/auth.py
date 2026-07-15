"""Account-service auth: shared JWT validation + local test-token minting.

Validation is delegated to the shared finans-tracker-auth package (P2-02).
``create_access_token`` stays local because the test suite mints tokens with
it; account-service itself never issues tokens at runtime (user-service does).

Monolith residue removed with the migration: password hashing (this service
has no users/passwords), ``TokenData``/``Token`` models, ``decode_token`` and
``verify_token_and_get_user_id`` — none had callers outside this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from auth.fastapi import make_current_user_dependency
from jose import jwt

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

# Fail fast at startup rather than 401'ing every request (P1-06).
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY must be set in environment variables. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )


def create_access_token(user_id: int, username: str, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """Opretter JWT access token for bruger"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta

    to_encode = {
        "sub": str(user_id),
        "user_id": user_id,
        "username": username,
        "email": email,
        "exp": expire,
    }

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


get_current_user_id = make_current_user_dependency(
    lambda: SECRET_KEY,
    algorithms=(ALGORITHM,),
)
