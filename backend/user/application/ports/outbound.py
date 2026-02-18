"""
Outbound ports (driven adapters) - interfaces for infrastructure.
These define what the User application needs from the outside world.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.user.domain.entities import User, UserWithCredentials


class IUserRepository(ABC):
    """Port for user persistence."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]:
        pass

    @abstractmethod
    def get_all(self) -> list[User]:
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        pass

    @abstractmethod
    def create(self, user: User, password_hash: str) -> User:
        """Create user with hashed password."""
        pass

    @abstractmethod
    def get_by_username_for_auth(
        self, username: str
    ) -> Optional[UserWithCredentials]:
        """Get user with credentials for authentication."""
        pass

    @abstractmethod
    def get_by_email_for_auth(
        self, email: str
    ) -> Optional[UserWithCredentials]:
        """Get user with credentials for authentication."""
        pass


class IAccountPort(ABC):
    """Anti-corruption port for account domain.

    Used to create default account on user registration
    and to resolve first account_id on login.
    """

    @abstractmethod
    def create_default_account(self, user_id: int) -> None:
        """Create a default 'Min Konto' account for a new user."""
        pass

    @abstractmethod
    def get_first_account_id(self, user_id: int) -> Optional[int]:
        """Get the first account ID for a user (used in login response)."""
        pass
