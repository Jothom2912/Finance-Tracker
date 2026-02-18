"""MySQL adapter for AccountGroup repository."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.account.application.ports.outbound import IAccountGroupRepository
from backend.account.domain.entities import AccountGroup, AccountGroupUser
from backend.models.mysql.account_groups import AccountGroups as AccountGroupModel
from backend.models.mysql.user import User as UserModel


class MySQLAccountGroupRepository(IAccountGroupRepository):
    """MySQL implementation of account group repository."""

    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, group_id: int) -> Optional[AccountGroup]:
        model = (
            self._db.query(AccountGroupModel)
            .filter(AccountGroupModel.idAccountGroups == group_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[AccountGroup]:
        models = (
            self._db.query(AccountGroupModel)
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def create(
        self, group: AccountGroup, user_ids: list[int]
    ) -> AccountGroup:
        model = AccountGroupModel(
            name=group.name,
            max_users=group.max_users,
        )

        if user_ids:
            users = (
                self._db.query(UserModel)
                .filter(UserModel.idUser.in_(user_ids))
                .all()
            )
            model.users.extend(users)

        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(
        self, group: AccountGroup, user_ids: list[int]
    ) -> AccountGroup:
        model = (
            self._db.query(AccountGroupModel)
            .filter(AccountGroupModel.idAccountGroups == group.id)
            .first()
        )

        model.name = group.name
        model.max_users = group.max_users

        if user_ids is not None:
            users = (
                self._db.query(UserModel)
                .filter(UserModel.idUser.in_(user_ids))
                .all()
            )
            model.users = users

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def _to_entity(self, model: AccountGroupModel) -> AccountGroup:
        users = [
            AccountGroupUser(id=u.idUser, username=u.username)
            for u in model.users
        ]
        return AccountGroup(
            id=model.idAccountGroups,
            name=model.name,
            max_users=getattr(model, "max_users", 20),
            users=users,
        )
