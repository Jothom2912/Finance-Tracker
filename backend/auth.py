# backend/auth.py
"""
Authentication module - Password hashing og JWT token generation + FastAPI integration
"""

from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import bcrypt

from backend.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from backend.database.mysql import get_db

# Validate SECRET_KEY at import time
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY must be set in environment variables. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================================================================
# MODELS FOR AUTH
# ============================================================================

class TokenData(BaseModel):
    """Data indeholdt i JWT token"""
    user_id: int
    username: str
    email: str


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
    """Hash password using bcrypt. Bcrypt has a 72-byte limit."""
    password = password[:72]
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    plain_password = plain_password[:72]
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================================
# JWT TOKEN FUNCTIONS
# ============================================================================

def create_access_token(
    user_id: int,
    username: str,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Opretter JWT access token for bruger"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    
    to_encode = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "exp": expire
    }
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[TokenData]:
    """Dekoder JWT token og returnerer data"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        username: str = payload.get("username")
        email: str = payload.get("email")
        
        if user_id is None or username is None or email is None:
            return None
        
        return TokenData(user_id=user_id, username=username, email=email)
    except JWTError:
        return None


# ============================================================================
# FASTAPI DEPENDENCIES
# ============================================================================

def get_current_user_id(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> int:
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

def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db),
) -> Optional[int]:
    """
    FastAPI Dependency: Resolves account_id from request headers.
    
    Priority:
    1. X-Account-ID header (explicit account selection)
    2. First account for the authenticated user (fallback via JWT)
    
    Returns:
        account_id if found, None otherwise
    """
    token_data: Optional[TokenData] = None
    if authorization:
        token = (
            authorization.replace("Bearer ", "")
            if authorization.startswith("Bearer ")
            else authorization
        )
        token_data = decode_token(token)

    if x_account_id:
        try:
            requested_account_id = int(x_account_id)
        except ValueError:
            requested_account_id = None

        # Explicit account selection requires a valid authenticated user.
        if requested_account_id is not None and token_data:
            from backend.repositories import get_account_repository

            account_repo = get_account_repository(db)
            account = account_repo.get_by_id(requested_account_id)
            if account and account.get("User_idUser") == token_data.user_id:
                return requested_account_id
        return None

    if token_data:
        from backend.repositories import get_account_repository

        account_repo = get_account_repository(db)
        accounts = account_repo.get_all(user_id=token_data.user_id)
        if accounts:
            return accounts[0]["idAccount"]

    return None


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
