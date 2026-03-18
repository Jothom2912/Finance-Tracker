"""
Cross-cutting auth contract.

Rule: this file may ONLY contain auth-related ports.
Keep it ultra-slim — this is NOT a shared dump.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class IAccountResolver(ABC):
    """Port for resolving account ownership from user credentials."""

    @abstractmethod
    def get_account_id_for_user(self, user_id: int) -> Optional[int]:
        """Return primary account_id for a given user_id."""
        ...

    @abstractmethod
    def verify_account_ownership(self, user_id: int, account_id: int) -> bool:
        """Verify that user_id owns account_id."""
        ...
