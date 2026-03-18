from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IUserRepository
from app.domain.entities import User, UserWithCredentials
from app.models import UserModel


class PostgresUserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, username: str, email: str, password_hash: str) -> UserWithCredentials:
        model = UserModel(
            username=username,
            email=email,
            password_hash=password_hash,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_credentials_entity(model)

    async def find_by_email(self, email: str) -> UserWithCredentials | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_credentials_entity(model) if model else None

    async def find_by_username(self, username: str) -> UserWithCredentials | None:
        stmt = select(UserModel).where(UserModel.username == username)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_credentials_entity(model) if model else None

    async def find_by_id(self, user_id: int) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_credentials_entity(model: UserModel) -> UserWithCredentials:
        return UserWithCredentials(
            id=model.id,
            username=model.username,
            email=model.email,
            password_hash=model.password_hash,
            created_at=model.created_at,
        )
