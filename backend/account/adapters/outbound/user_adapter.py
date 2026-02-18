"""Anti-corruption layer for User domain.

Implements the Account domain's IUserPort."""

from sqlalchemy.orm import Session

from backend.account.application.ports.outbound import IUserPort
from backend.models.mysql.user import User as UserModel


class MySQLUserAdapter(IUserPort):
    """Anti-corruption layer for user domain."""

    def __init__(self, db: Session):
        self._db = db

    def exists(self, user_id: int) -> bool:
        return (
            self._db.query(UserModel)
            .filter(UserModel.idUser == user_id)
            .first()
        ) is not None

    def get_users_by_ids(
        self, user_ids: list[int]
    ) -> list[tuple[int, str]]:
        users = (
            self._db.query(UserModel)
            .filter(UserModel.idUser.in_(user_ids))
            .all()
        )
        return [(u.idUser, u.username) for u in users]
