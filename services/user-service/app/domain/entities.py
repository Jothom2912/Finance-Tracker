from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """User domain entity without credentials."""

    id: int
    username: str
    email: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class UserWithCredentials:
    """User with password hash — only used in authentication flows.

    Separated from User to prevent credentials from leaking into
    read operations.
    """

    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime | None = None
