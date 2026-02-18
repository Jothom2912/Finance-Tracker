"""Outbound ports (driven adapters) for Account bounded context.

Defines interfaces for infrastructure dependencies."""

from abc import ABC, abstractmethod
from typing import Optional

from backend.account.domain.entities import Account, AccountGroup


class IAccountRepository(ABC):
    """Port for account persistence."""

    @abstractmethod
    def get_by_id(self, account_id: int) -> Optional[Account]:
        pass

    @abstractmethod
    def get_all(self, user_id: int) -> list[Account]:
        pass

    @abstractmethod
    def create(self, account: Account) -> Account:
        pass

    @abstractmethod
    def update(self, account: Account) -> Account:
        pass

    @abstractmethod
    def delete(self, account_id: int) -> bool:
        pass


class IAccountGroupRepository(ABC):
    """Port for account group persistence."""

    @abstractmethod
    def get_by_id(self, group_id: int) -> Optional[AccountGroup]:
        pass

    @abstractmethod
    def get_all(self, skip: int = 0, limit: int = 100) -> list[AccountGroup]:
        pass

    @abstractmethod
    def create(self, group: AccountGroup, user_ids: list[int]) -> AccountGroup:
        pass

    @abstractmethod
    def update(self, group: AccountGroup, user_ids: list[int]) -> AccountGroup:
        pass


class IUserPort(ABC):
    """Anti-corruption port for user domain."""

    @abstractmethod
    def exists(self, user_id: int) -> bool:
        pass

    @abstractmethod
    def get_users_by_ids(self, user_ids: list[int]) -> list[tuple[int, str]]:
        """Returns list of (user_id, username) tuples for valid users."""
        pass
