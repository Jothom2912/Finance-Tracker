"""
MySQL implementation of User repository port.
"""
from typing import Optional

from sqlalchemy.orm import Session

from backend.user.application.ports.outbound import IUserRepository
from backend.user.domain.entities import User, UserWithCredentials
from backend.models.mysql.user import User as UserModel


class MySQLUserRepository(IUserRepository):
    """MySQL implementation of user repository."""

    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        model = (
            self._db.query(UserModel)
            .filter(UserModel.idUser == user_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self) -> list[User]:
        models = self._db.query(UserModel).all()
        return [self._to_entity(m) for m in models]

    def get_by_username(self, username: str) -> Optional[User]:
        model = (
            self._db.query(UserModel)
            .filter(UserModel.username == username)
            .first()
        )
        return self._to_entity(model) if model else None

    def create(self, user: User, password_hash: str) -> User:
        model = UserModel(
            username=user.username,
            email=user.email,
            password=password_hash,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def get_by_username_for_auth(
        self, username: str
    ) -> Optional[UserWithCredentials]:
        """Get user with credentials by username for authentication."""
        model = (
            self._db.query(UserModel)
            .filter(UserModel.username == username)
            .first()
        )
        return self._to_auth_entity(model) if model else None

    def get_by_email_for_auth(
        self, email: str
    ) -> Optional[UserWithCredentials]:
        """Get user with credentials by email for authentication."""
        model = (
            self._db.query(UserModel)
            .filter(UserModel.email == email)
            .first()
        )
        return self._to_auth_entity(model) if model else None

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.idUser,
            username=model.username,
            email=model.email,
            created_at=model.created_at,
        )

    def _to_auth_entity(self, model: UserModel) -> UserWithCredentials:
        return UserWithCredentials(
            id=model.idUser,
            username=model.username,
            email=model.email,
            password_hash=model.password,
            created_at=model.created_at,
        )
