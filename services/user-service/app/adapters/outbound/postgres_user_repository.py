from __future__ import annotations

import logging
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IUserRepository
from app.domain.entities import User, UserWithCredentials
from app.domain.exceptions import UserNotFoundException
from app.models import UserModel

logger = logging.getLogger(__name__)


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

    async def find_credentials_by_id(self, user_id: int) -> UserWithCredentials | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_credentials_entity(model) if model else None

    async def update_password(self, user_id: int, password_hash: str) -> None:
        await self._update(user_id, password_hash=password_hash)

    async def update_username(self, user_id: int, username: str) -> User:
        await self._update(user_id, username=username)
        # Re-læs frem for RETURNING: aiosqlite i testene og Postgres i drift
        # skal opføre sig ens, og en ekstra SELECT inde i samme transaktion
        # er billigere end at fejle forskelligt de to steder.
        model = await self._session.get(UserModel, user_id)
        if model is None:  # pragma: no cover — _update har lige bevist rækken findes
            raise UserNotFoundException(user_id)
        return self._to_entity(model)

    async def _update(self, user_id: int, **values: str) -> None:
        """Skriv felter på en eksisterende bruger og stempl ``updated_at``.

        Tidsstemplet kommer fra databasens ur (``func.now()``), ikke fra
        processens — samme kilde som ``created_at``s server_default, så de
        to felter er sammenlignelige, og der er intet ``datetime.now()`` at
        injicere et ur udenom.

        Commit ejes af UoW'en som i ``create``.
        """
        stmt = update(UserModel).where(UserModel.id == user_id).values(updated_at=func.now(), **values)
        # execute() er typet som Result[Any] for enhver statement; en DML
        # giver i praksis en CursorResult, som er den der bærer rowcount.
        result = cast(CursorResult[Any], await self._session.execute(stmt))
        if result.rowcount == 0:
            # Brugeren blev slettet mellem use casens opslag og denne skrivning.
            # Et tavst no-op ville svare 200/204 på en ændring der ikke skete.
            #
            # P3-59: 404'en der følger er ikke til at skelne fra "brugeren fandtes aldrig",
            # men dette sted VED at den fandtes for et øjeblik siden — use casen slog den
            # op.  Den viden findes kun her, og den er forskellen på en TOCTOU-race og et
            # ganske almindeligt opslag på et forkert id.  Feltnavnene, ikke værdierne:
            # `values` indeholder password-hash på password-stien.
            logger.warning(
                "TOCTOU: bruger %s fandtes ved use casens opslag men ikke ved skrivningen (felter=%s)",
                user_id,
                sorted(values),
            )
            raise UserNotFoundException(user_id)
        await self._session.flush()

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
