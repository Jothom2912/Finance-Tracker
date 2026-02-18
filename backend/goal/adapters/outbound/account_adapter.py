"""
Anti-corruption layer for Account domain.
Allows Goal domain to check account existence without coupling to Account internals.
"""
from sqlalchemy.orm import Session

from backend.goal.application.ports.outbound import IAccountPort
from backend.models.mysql.account import Account as AccountModel


class MySQLAccountAdapter(IAccountPort):
    """MySQL implementation of account port for goal domain."""

    def __init__(self, db: Session):
        self._db = db

    def exists(self, account_id: int) -> bool:
        return (
            self._db.query(AccountModel)
            .filter(AccountModel.idAccount == account_id)
            .first()
        ) is not None
