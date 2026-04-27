# backend/auth.py
"""
Authentication module - Password hashing og JWT token generation + FastAPI integration
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY


# Validate SECRET_KEY at import time
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY must be set in environment variables. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _bcrypt_rounds() -> int:
    """Bcrypt cost factor, read per call so tests can override via
    ``BCRYPT_ROUNDS=4``.  Default 12 is safe for production.  Minimum
    allowed by bcrypt spec is 4.  Each +1 doubles the hashing time.
    """
    try:
        return max(4, int(os.environ.get("BCRYPT_ROUNDS", "12")))
    except (TypeError, ValueError):
        return 12


# ============================================================================
# MODELS FOR AUTH
# ============================================================================


class TokenData(BaseModel):
    """Data indeholdt i JWT token"""

    user_id: int
    username: Optional[str] = None
    email: Optional[str] = None


class Token(BaseModel):
    """Response ved login"""

    access_token: str
    token_type: str
    user_id: int
    username: str
    email: str


# ============================================================================
# PASSWORD FUNCTIONS
# ============================================================================


def hash_password(password: str) -> str:
    """Hash password using bcrypt. Bcrypt has a 72-byte limit.

    Cost factor is read from ``BCRYPT_ROUNDS`` (default 12).
    """
    password = password[:72]
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=_bcrypt_rounds()))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    plain_password = plain_password[:72]
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================================
# JWT TOKEN FUNCTIONS
# ============================================================================


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


def decode_token(token: str) -> Optional[TokenData]:
    """Dekoder JWT token og returnerer data.

    Accepts both monolith format (``user_id`` claim) and
    microservice format (``sub`` claim) for cross-service
    JWT compatibility.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

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


# ============================================================================
# FASTAPI DEPENDENCIES
# ============================================================================


def get_current_user_id(authorization: Optional[str] = Header(None, alias="Authorization")) -> int:
    """
    FastAPI Dependency: Henter current user ID fra JWT token i Authorization header.

    Kan bruges i alle routers der kræver authentication.

    Args:
        authorization: Authorization header fra request (format: "Bearer <token>")

    Returns:
        user_id fra token

    Raises:
        HTTPException 401 hvis token mangler eller er ugyldig
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Split "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    token_data = decode_token(token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data.user_id


# ============================================================================
# ACCOUNT RESOLUTION DEPENDENCY
# ============================================================================


# def get_account_id_from_headers(
#     authorization: Optional[str] = Header(None, alias="Authorization"),
#     x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
#     resolver: IAccountResolver = Depends(get_account_resolver),
# ) -> Optional[int]:
#     """
#     FastAPI Dependency: Resolves account_id from request headers.

#     Priority:
#     1. X-Account-ID header (explicit account selection)
#     2. First account for the authenticated user (fallback via JWT)

#     Returns:
#         account_id if found, None otherwise
#     """
#     token_data: Optional[TokenData] = None
#     if authorization:
#         token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
#         token_data = decode_token(token)

#     if x_account_id:
#         try:
#             requested_account_id = int(x_account_id)
#         except ValueError:
#             requested_account_id = None

#         if requested_account_id is not None and token_data:
#             if resolver.verify_account_ownership(token_data.user_id, requested_account_id):
#                 return requested_account_id
#         return None

#     if token_data:
#         return resolver.get_account_id_for_user(token_data.user_id)

#     return None


# ============================================================================
# HELPERS
# ============================================================================


def verify_token_and_get_user_id(token: str) -> Optional[int]:
    """
    Hjælpefunktion: Dekoder token og returnerer user_id

    Returns:
        user_id hvis valid token, None hvis invalid
    """
    token_data = decode_token(token)
    if token_data is None:
        return None
    return token_data.user_id
