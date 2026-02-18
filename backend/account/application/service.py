"""Application service for Account bounded context.

Orchestrates use cases using domain entities and ports."""

import logging
from typing import Optional

from backend.account.application.ports.inbound import IAccountService
from backend.account.application.ports.outbound import (
    IAccountRepository,
    IAccountGroupRepository,
    IUserPort,
)
from backend.account.domain.entities import Account, AccountGroup
from backend.account.domain.exceptions import (
    UserNotFoundForAccount,
    InvalidUserInGroup,
)
from backend.shared.schemas.account import (
    AccountCreate,
    AccountBase,
    Account as AccountSchema,
)
from backend.shared.schemas.account_groups import (
    AccountGroupsCreate,
    AccountGroups as AccountGroupSchema,
)

logger = logging.getLogger(__name__)


class AccountService(IAccountService):
    """Account service implementing business logic."""

    def __init__(
        self,
        account_repository: IAccountRepository,
        account_group_repository: IAccountGroupRepository,
        user_port: IUserPort,
    ):
        self._account_repo = account_repository
        self._group_repo = account_group_repository
        self._user_port = user_port

    # ------------------------------------------------------------------
    # Account methods
    # ------------------------------------------------------------------

    def get_account(self, account_id: int) -> Optional[AccountSchema]:
        account = self._account_repo.get_by_id(account_id)
        if not account:
            return None
        return self._account_to_dto(account)

    def list_accounts(self, user_id: int) -> list[AccountSchema]:
        accounts = self._account_repo.get_all(user_id)
        return [self._account_to_dto(a) for a in accounts]

    def create_account(self, data: AccountCreate) -> AccountSchema:
        if not self._user_port.exists(data.User_idUser):
            raise UserNotFoundForAccount(data.User_idUser)

        account = Account(
            id=None,
            name=data.name,
            saldo=data.saldo,
            user_id=data.User_idUser,
        )

        created = self._account_repo.create(account)
        return self._account_to_dto(created)

    def update_account(
        self, account_id: int, data: AccountBase
    ) -> Optional[AccountSchema]:
        existing = self._account_repo.get_by_id(account_id)
        if not existing:
            return None

        updated_account = Account(
            id=account_id,
            name=data.name,
            saldo=data.saldo,
            user_id=existing.user_id,
        )

        result = self._account_repo.update(updated_account)
        return self._account_to_dto(result)

    # ------------------------------------------------------------------
    # Account Group methods
    # ------------------------------------------------------------------

    def get_group(self, group_id: int) -> Optional[AccountGroupSchema]:
        group = self._group_repo.get_by_id(group_id)
        if not group:
            return None
        return self._group_to_dto(group)

    def list_groups(
        self, skip: int = 0, limit: int = 100
    ) -> list[AccountGroupSchema]:
        groups = self._group_repo.get_all(skip=skip, limit=limit)
        return [self._group_to_dto(g) for g in groups]

    def create_group(self, data: AccountGroupsCreate) -> AccountGroupSchema:
        user_ids = data.user_ids or []

        # Validate users exist
        if user_ids:
            valid_users = self._user_port.get_users_by_ids(user_ids)
            if len(valid_users) != len(user_ids):
                raise InvalidUserInGroup()

        group = AccountGroup(
            id=None,
            name=data.name,
            max_users=data.max_users or 20,
            users=[],
        )

        created = self._group_repo.create(group, user_ids)
        return self._group_to_dto(created)

    def update_group(
        self, group_id: int, data: AccountGroupsCreate
    ) -> Optional[AccountGroupSchema]:
        existing = self._group_repo.get_by_id(group_id)
        if not existing:
            return None

        user_ids = data.user_ids or []

        # Validate users exist
        if user_ids:
            valid_users = self._user_port.get_users_by_ids(user_ids)
            if len(valid_users) != len(user_ids):
                raise InvalidUserInGroup()

        updated_group = AccountGroup(
            id=group_id,
            name=data.name,
            max_users=data.max_users or existing.max_users,
            users=[],
        )

        result = self._group_repo.update(updated_group, user_ids)
        return self._group_to_dto(result)

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _account_to_dto(self, account: Account) -> AccountSchema:
        return AccountSchema(
            idAccount=account.id,
            name=account.name,
            saldo=account.saldo,
            User_idUser=account.user_id,
        )

    def _group_to_dto(self, group: AccountGroup) -> AccountGroupSchema:
        return AccountGroupSchema(
            idAccountGroups=group.id,
            name=group.name,
            max_users=group.max_users,
            users=[
                {"idUser": u.id, "username": u.username} for u in group.users
            ],
        )
