from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from contracts.events.user import UserCreatedEvent

from app.application.dto import (
    LoginDTO,
    RegisterDTO,
    TokenResponse,
    UserResponse,
)
from app.application.ports.inbound import IUserService
from app.application.ports.outbound import IUnitOfWork
from app.domain.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

logger = logging.getLogger(__name__)


class UserService(IUserService):
    """Application service implementing user use cases.

    Uses a Unit of Work that exposes both the user repository and
    the transactional outbox.  Domain writes and outbox inserts
    happen in the same database transaction — eliminating the
    dual-write problem between DB and message broker.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        hash_password: Callable[[str], str],
        verify_password: Callable[[str, str], bool],
        create_token: Callable[[int, str, str], str],
    ) -> None:
        self._uow = uow
        self._hash_password = hash_password
        self._verify_password = verify_password
        self._create_token = create_token

    async def register(self, dto: RegisterDTO) -> UserResponse:
        async with self._uow:
            if await self._uow.users.find_by_email(dto.email):
                raise UserAlreadyExistsException("email", dto.email)

            if await self._uow.users.find_by_username(dto.username):
                raise UserAlreadyExistsException("username", dto.username)

            password_hash = self._hash_password(dto.password)

            user = await self._uow.users.create(
                username=dto.username,
                email=dto.email,
                password_hash=password_hash,
            )

            await self._uow.outbox.add(
                event=UserCreatedEvent(
                    user_id=user.id,
                    email=user.email,
                    username=user.username,
                ),
                aggregate_type="user",
                aggregate_id=str(user.id),
            )

            await self._uow.commit()

        logger.info("Registered user %s (outbox event queued)", user.id)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at or datetime.now(timezone.utc),
        )

    async def login(self, dto: LoginDTO) -> TokenResponse:
        async with self._uow:
            identifier = dto.username_or_email
            if "@" in identifier:
                user = await self._uow.users.find_by_email(identifier)
            else:
                user = await self._uow.users.find_by_username(identifier)

        if user is None:
            raise InvalidCredentialsException()

        if not self._verify_password(dto.password, user.password_hash):
            raise InvalidCredentialsException()

        access_token = self._create_token(user.id, user.username, user.email)

        return TokenResponse(
            access_token=access_token,
            user_id=user.id,
            username=user.username,
        )

    async def get_user(self, user_id: int) -> UserResponse:
        async with self._uow:
            user = await self._uow.users.find_by_id(user_id)

        if user is None:
            raise UserNotFoundException(user_id)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at or datetime.now(timezone.utc),
        )

    async def user_exists(self, user_id: int) -> bool:
        async with self._uow:
            user = await self._uow.users.find_by_id(user_id)
        return user is not None
