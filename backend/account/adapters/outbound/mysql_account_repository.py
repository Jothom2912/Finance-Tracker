"""MySQL adapter for Account repository."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.account.application.ports.outbound import IAccountRepository
from backend.account.domain.entities import Account
from backend.models.mysql.account import Account as AccountModel


class MySQLAccountRepository(IAccountRepository):
    """MySQL implementation of account repository."""

    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, account_id: int) -> Optional[Account]:
        model = (
            self._db.query(AccountModel)
            .filter(AccountModel.idAccount == account_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self, user_id: int) -> list[Account]:
        models = (
            self._db.query(AccountModel)
            .filter(AccountModel.User_idUser == user_id)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def create(self, account: Account) -> Account:
        model = AccountModel(
            name=account.name,
            saldo=account.saldo,
            User_idUser=account.user_id,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(self, account: Account) -> Account:
        model = (
            self._db.query(AccountModel)
            .filter(AccountModel.idAccount == account.id)
            .first()
        )

        model.name = account.name
        model.saldo = account.saldo

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def delete(self, account_id: int) -> bool:
        model = (
            self._db.query(AccountModel)
            .filter(AccountModel.idAccount == account_id)
            .first()
        )
        if not model:
            return False

        self._db.delete(model)
        self._db.commit()
        return True

    def _to_entity(self, model: AccountModel) -> Account:
        return Account(
            id=model.idAccount,
            name=model.name,
            saldo=float(model.saldo) if model.saldo else 0.0,
            user_id=model.User_idUser,
        )
