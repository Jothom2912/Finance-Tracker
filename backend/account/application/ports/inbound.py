"""Inbound ports (driving adapters) for Account bounded context.

Defines the service interface for external consumers."""

from abc import ABC, abstractmethod
from typing import Optional

from backend.shared.schemas.account import (
    AccountCreate,
    AccountBase,
    Account as AccountSchema,
)
from backend.shared.schemas.account_groups import (
    AccountGroupsCreate,
    AccountGroups as AccountGroupSchema,
)


class IAccountService(ABC):
    """Inbound port defining account use cases."""

    # Account methods
    @abstractmethod
    def get_account(self, account_id: int) -> Optional[AccountSchema]:
        pass

    @abstractmethod
    def list_accounts(self, user_id: int) -> list[AccountSchema]:
        pass

    @abstractmethod
    def create_account(self, data: AccountCreate) -> AccountSchema:
        pass

    @abstractmethod
    def update_account(
        self, account_id: int, data: AccountBase
    ) -> Optional[AccountSchema]:
        pass

    # Account Group methods
    @abstractmethod
    def get_group(self, group_id: int) -> Optional[AccountGroupSchema]:
        pass

    @abstractmethod
    def list_groups(
        self, skip: int = 0, limit: int = 100
    ) -> list[AccountGroupSchema]:
        pass

    @abstractmethod
    def create_group(self, data: AccountGroupsCreate) -> AccountGroupSchema:
        pass

    @abstractmethod
    def update_group(
        self, group_id: int, data: AccountGroupsCreate
    ) -> Optional[AccountGroupSchema]:
        pass
