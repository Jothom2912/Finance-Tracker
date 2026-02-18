"""Data Transfer Objects for Goal bounded context."""

# Re-export shared schemas as application DTO aliases
from backend.shared.schemas.goal import (  # noqa: F401
    Goal,
    GoalCreate,
    GoalBase,
)
