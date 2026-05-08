"""Application service for Account bounded context.

Orchestrates use cases using domain entities and ports."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.application.dto import (
    Account as AccountSchema,
)
from app.application.dto import (
    AccountBase,
    AccountCreate,
    AccountGroupsCreate,
)
from app.application.dto import (
    AccountGroups as AccountGroupSchema,
)
from app.application.ports.inbound import IAccountService
from app.application.ports.outbound import (
    IAccountGroupRepository,
    IAccountRepository,
    IUserPort,
)
from app.domain.entities import Account, AccountGroup
from app.domain.exceptions import (
    InvalidUserInGroup,
    UserNotFoundForAccount,
)

if TYPE_CHECKING:
    from app.adapters.outbound.outbox_repository import SyncOutboxRepository

logger = logging.getLogger(__name__)


class AccountService(IAccountService):
    """Account service implementing business logic."""

    def __init__(
        self,
        account_repository: IAccountRepository,
        account_group_repository: IAccountGroupRepository,
        user_port: IUserPort,
        outbox: Optional[SyncOutboxRepository] = None,
        commit_fn: Optional[callable] = None,
    ):
        self._account_repo = account_repository
        self._group_repo = account_group_repository
        self._user_port = user_port
        self._outbox = outbox
        self._commit = commit_fn

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
            budget_start_day=data.budget_start_day,
        )

        created = self._account_repo.create(account)

        if self._outbox:
            self._outbox.add(
                event_type="account.created",
                payload={
                    "event_type": "account.created",
                    "event_version": 1,
                    "account_id": created.id,
                    "user_id": created.user_id,
                    "account_name": created.name,
                    "saldo": str(created.saldo),
                    "budget_start_day": created.budget_start_day,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                aggregate_type="account",
                aggregate_id=str(created.id),
            )

        if self._commit:
            self._commit()

        return self._account_to_dto(created)

    def update_account(self, account_id: int, data: AccountBase) -> Optional[AccountSchema]:
        existing = self._account_repo.get_by_id(account_id)
        if not existing:
            return None

        updated_account = Account(
            id=account_id,
            name=data.name,
            saldo=data.saldo,
            user_id=existing.user_id,
            budget_start_day=data.budget_start_day,
        )

        result = self._account_repo.update(updated_account)

        if self._outbox:
            self._outbox.add(
                event_type="account.updated",
                payload={
                    "event_type": "account.updated",
                    "event_version": 1,
                    "account_id": result.id,
                    "user_id": result.user_id,
                    "name": result.name,
                    "saldo": str(result.saldo),
                    "budget_start_day": result.budget_start_day,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                aggregate_type="account",
                aggregate_id=str(result.id),
            )

        if self._commit:
            self._commit()

        return self._account_to_dto(result)

    # ------------------------------------------------------------------
    # Account Group methods
    # ------------------------------------------------------------------

    def get_group(self, group_id: int) -> Optional[AccountGroupSchema]:
        group = self._group_repo.get_by_id(group_id)
        if not group:
            return None
        return self._group_to_dto(group)

    def list_groups(self, skip: int = 0, limit: int = 100) -> list[AccountGroupSchema]:
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

    def update_group(self, group_id: int, data: AccountGroupsCreate) -> Optional[AccountGroupSchema]:
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
            budget_start_day=account.budget_start_day,
        )

    def _group_to_dto(self, group: AccountGroup) -> AccountGroupSchema:
        return AccountGroupSchema(
            idAccountGroups=group.id,
            name=group.name,
            max_users=group.max_users,
            users=[{"idUser": u.id, "username": u.username} for u in group.users],
        )
