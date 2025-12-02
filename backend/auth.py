# backend/auth.py
"""
Authentication module - Håndterer password hashing og JWT token generation
"""

from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

# ============================================================================
# KONFIGURATION
# ============================================================================

# JWT Configuration
SECRET_KEY = "your-secret-key-change-this-in-production"  # ⚠️ SKIFT DETTE I PRODUCTION
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # Token udløber efter 60 minutter

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Import bcrypt directly for more control
import bcrypt

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
    # Truncate password to 72 characters (before encoding to bytes)
    password = password[:72]
    # Encode to bytes
    password_bytes = password.encode('utf-8')
    # Hash using bcrypt directly
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
    # Return as string
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password. Bcrypt has a 72-byte limit."""
    # Truncate password to 72 characters (before encoding to bytes)
    plain_password = plain_password[:72]
    # Encode to bytes
    password_bytes = plain_password.encode('utf-8')
    # Hash must be encoded as bytes too
    hashed_bytes = hashed_password.encode('utf-8')
    # Use bcrypt directly
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
    """
    Opretter JWT access token for bruger
    
    Args:
        user_id: Brugerens ID
        username: Brugerens username
        email: Brugerens email
        expires_delta: Hvor længe token er gyldigt (default: 60 min)
    
    Returns:
        JWT token som string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    
    # Data der skal være i token
    to_encode = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "exp": expire
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    Dekoder JWT token og returnerer data
    
    Args:
        token: JWT token
    
    Returns:
        TokenData hvis valid, None hvis invalid
    """
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
