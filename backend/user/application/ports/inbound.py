"""
Inbound ports (driving adapters) - interfaces for use cases.
These define what the User application can do.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.shared.schemas.user import (
    UserCreate,
    User as UserSchema,
)


class IUserService(ABC):
    """Inbound port defining user use cases."""

    @abstractmethod
    def get_user(self, user_id: int) -> Optional[UserSchema]:
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[UserSchema]:
        pass

    @abstractmethod
    def list_users(
        self, skip: int = 0, limit: int = 100
    ) -> list[UserSchema]:
        pass

    @abstractmethod
    def create_user(self, data: UserCreate) -> UserSchema:
        pass

    @abstractmethod
    def login_user(self, username_or_email: str, password: str) -> dict:
        pass
