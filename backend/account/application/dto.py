"""Data Transfer Objects for Account bounded context."""

# Re-export shared schemas as application DTO aliases
from backend.shared.schemas.account import (  # noqa: F401
    Account,
    AccountCreate,
    AccountBase,
)
from backend.shared.schemas.account_groups import (  # noqa: F401
    AccountGroups,
    AccountGroupsCreate,
)
