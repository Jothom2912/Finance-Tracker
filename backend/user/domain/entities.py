"""
Domain entities for User bounded context.
Pure domain objects with no infrastructure dependencies.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User domain entity (without credentials)."""
    id: Optional[int]
    username: str
    email: str
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.username:
            raise ValueError("Username is required")
        if not self.email:
            raise ValueError("Email is required")


@dataclass
class UserWithCredentials:
    """User with password hash - only used for authentication flows.

    This entity is intentionally separate from User to enforce
    that credentials are never accidentally exposed in read operations.
    """
    id: int
    username: str
    email: str
    password_hash: str
    created_at: Optional[datetime] = None
