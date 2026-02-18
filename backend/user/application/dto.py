"""Data Transfer Objects for User bounded context."""

# Re-export shared schemas as application DTO aliases
from backend.shared.schemas.user import (  # noqa: F401
    User,
    UserCreate,
    UserLogin,
    TokenResponse,
)
