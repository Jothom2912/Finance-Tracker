"""
Anti-corruption layer for Account domain.
Allows User domain to create default accounts and resolve account IDs
without coupling to Account internals.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.user.application.ports.outbound import IAccountPort
from backend.models.mysql.account import Account as AccountModel

logger = logging.getLogger(__name__)


class MySQLAccountAdapter(IAccountPort):
    """MySQL implementation of account port for user domain."""

    def __init__(self, db: Session):
        self._db = db

    def create_default_account(self, user_id: int) -> None:
        """Create a default 'Min Konto' account for a new user."""
        model = AccountModel(
            name="Min Konto",
            saldo=0.0,
            User_idUser=user_id,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        logger.info(
            "Default account %s created for user %s",
            model.idAccount,
            user_id,
        )

    def get_first_account_id(self, user_id: int) -> Optional[int]:
        """Get the first account ID for a user."""
        model = (
            self._db.query(AccountModel)
            .filter(AccountModel.User_idUser == user_id)
            .first()
        )
        return model.idAccount if model else None
