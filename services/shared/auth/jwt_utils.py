"""Shared JWT validation utilities for all microservices."""

from datetime import datetime, timedelta

import jwt
from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    iat: datetime


def create_access_token(
    subject: str,
    secret_key: str,
    expires_delta: timedelta = timedelta(hours=1),
) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_token(token: str, secret_key: str) -> TokenPayload:
    decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
    return TokenPayload(**decoded)
