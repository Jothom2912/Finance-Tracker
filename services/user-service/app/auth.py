from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from auth.fastapi import make_current_user_dependency
from jose import jwt

from app.config import settings

_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    password_bytes = password[:_BCRYPT_MAX_BYTES].encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    plain_bytes = plain[:_BCRYPT_MAX_BYTES].encode("utf-8")
    hashed_bytes = hashed.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(user_id: int, username: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "username": username,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# Token *validation* is delegated to the shared finans-tracker-auth package;
# token *minting* (create_access_token) and password hashing stay here —
# user-service is the only issuer.
get_current_user_id = make_current_user_dependency(
    lambda: settings.JWT_SECRET,
    algorithms=(settings.JWT_ALGORITHM,),
)
