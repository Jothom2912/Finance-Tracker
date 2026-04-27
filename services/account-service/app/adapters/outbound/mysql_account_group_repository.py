"""MySQL adapter for AccountGroup repository."""

from typing import Optional

from sqlalchemy.orm import Session

from app.application.ports.outbound import IAccountGroupRepository
from app.domain.entities import AccountGroup, AccountGroupUser
from app.models.account_groups import AccountGroups as AccountGroupModel
from app.adapters.outbound.user_adapter import UserServiceAdapter



class MySQLAccountGroupRepository(IAccountGroupRepository):
    """MySQL implementation of account group repository."""

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
        if user_ids:
            users = self._user_adapter.get_users_by_ids(user_ids)
            # midlertidigt: vi gemmer ikke relationen i DB
            # kun validerer at users findes

        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(self, group: AccountGroup, user_ids: list[int]) -> AccountGroup:
        model = self._db.query(AccountGroupModel).filter(AccountGroupModel.idAccountGroups == group.id).first()

        model.name = group.name
        model.max_users = group.max_users
        
        if user_ids is not None:
            users = self._user_adapter.get_users_by_ids(user_ids)
            # samme her: ingen DB relation endnu

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def _to_entity(self, model: AccountGroupModel) -> AccountGroup:
        return AccountGroup(
            id=model.idAccountGroups,
            name=model.name,
            max_users=getattr(model, "max_users", 20),
            users=[]  # midlertidigt tom
    )
