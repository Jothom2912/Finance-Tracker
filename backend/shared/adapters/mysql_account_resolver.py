"""
MySQL adapter for IAccountResolver.

Read-only — no commit/rollback. Uses injected session.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.models.mysql.account import Account as AccountModel
from backend.shared.ports.auth_ports import IAccountResolver


class MySQLAccountResolver(IAccountResolver):
    """Resolves account ownership via direct SQLAlchemy queries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_account_id_for_user(self, user_id: int) -> Optional[int]:
        account = (
            self._session.query(AccountModel)
            .filter(AccountModel.User_idUser == user_id)
            .first()
        )
        if account is None:
            return None
        return account.idAccount

    def verify_account_ownership(self, user_id: int, account_id: int) -> bool:
        account = (
            self._session.query(AccountModel)
            .filter(
                AccountModel.idAccount == account_id,
                AccountModel.User_idUser == user_id,
            )
            .first()
        )
        return account is not None
