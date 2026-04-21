"""
Anti-corruption layer for Account domain.
Allows Goal domain to check account existence without coupling to Account internals.
"""

from typing import Optional

from app.application.ports.outbound import IAccountPort


class MockAccountAdapter(IAccountPort):
    """Mock implementation of account port for development."""

    async def exists(self, account_id: int) -> bool:
        """Check if account exists."""
        # TODO: Implement with real service call to user-service
        # For now, return True for all accounts
        return True
