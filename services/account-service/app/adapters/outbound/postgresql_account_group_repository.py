"""PostgreSQL adapter for AccountGroup repository."""

from typing import Optional

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.adapters.outbound.user_adapter import UserServiceAdapter
from app.application.ports.outbound import IAccountGroupRepository
from app.domain.entities import AccountGroup, AccountGroupUser
from app.models.account_groups import AccountGroups as AccountGroupModel
from app.models.common import account_group_user_association


class PostgresAccountGroupRepository(IAccountGroupRepository):
    """PostgreSQL implementation of account group repository."""

    def __init__(self, db: Session):
        self._db = db
        self._user_adapter = UserServiceAdapter()

    def get_by_id(self, group_id: int) -> Optional[AccountGroup]:
        model = self._db.query(AccountGroupModel).filter(AccountGroupModel.idAccountGroups == group_id).first()
        return self._to_entity(model) if model else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[AccountGroup]:
        models = self._db.query(AccountGroupModel).offset(skip).limit(limit).all()
        return [self._to_entity(m) for m in models]

    def create(self, group: AccountGroup, user_ids: list[int]) -> AccountGroup:
        model = AccountGroupModel(
            name=group.name,
            max_users=group.max_users,
        )

        self._db.add(model)
        self._db.flush()
        self._replace_users(model.idAccountGroups, user_ids)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(self, group: AccountGroup, user_ids: list[int]) -> AccountGroup:
        model = self._db.query(AccountGroupModel).filter(AccountGroupModel.idAccountGroups == group.id).first()

        model.name = group.name
        model.max_users = group.max_users
        self._replace_users(model.idAccountGroups, user_ids)

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def _replace_users(self, group_id: int, user_ids: list[int]) -> None:
        unique_user_ids = list(dict.fromkeys(user_ids))
        self._db.execute(
            delete(account_group_user_association).where(
                account_group_user_association.c.AccountGroups_idAccountGroups == group_id
            )
        )
        if not unique_user_ids:
            return

        self._db.execute(
            insert(account_group_user_association),
            [
                {
                    "AccountGroups_idAccountGroups": group_id,
                    "User_idUser": user_id,
                }
                for user_id in unique_user_ids
            ],
        )

    def _get_user_ids(self, group_id: int) -> list[int]:
        result = self._db.execute(
            select(account_group_user_association.c.User_idUser).where(
                account_group_user_association.c.AccountGroups_idAccountGroups == group_id
            )
        )
        return list(result.scalars().all())

    def _to_entity(self, model: AccountGroupModel) -> AccountGroup:
        user_ids = self._get_user_ids(model.idAccountGroups)
        users = [
            AccountGroupUser(id=user_id, username=username)
            for user_id, username in self._user_adapter.get_users_by_ids(user_ids)
        ]
        return AccountGroup(
            id=model.idAccountGroups,
            name=model.name,
            max_users=getattr(model, "max_users", 20),
            users=users,
        )
