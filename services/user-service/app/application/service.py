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
from app.application.ports.outbound import IEventPublisher, IUserRepository
from app.domain.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

logger = logging.getLogger(__name__)


class UserService(IUserService):
    """Application service implementing user use cases.

    All infrastructure dependencies are constructor-injected as ports
    or pure callables so the service layer stays free of framework
    and library imports.
    """

    def __init__(
        self,
        repository: IUserRepository,
        event_publisher: IEventPublisher,
        hash_password: Callable[[str], str],
        verify_password: Callable[[str, str], bool],
        create_token: Callable[[int], str],
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher
        self._hash_password = hash_password
        self._verify_password = verify_password
        self._create_token = create_token

    async def register(self, dto: RegisterDTO) -> UserResponse:
        if await self._repository.find_by_email(dto.email):
            raise UserAlreadyExistsException("email", dto.email)

        if await self._repository.find_by_username(dto.username):
            raise UserAlreadyExistsException("username", dto.username)

        password_hash = self._hash_password(dto.password)

        user = await self._repository.create(
            username=dto.username,
            email=dto.email,
            password_hash=password_hash,
        )

        event = UserCreatedEvent(
            user_id=user.id,
            email=user.email,
            username=user.username,
        )
        await self._event_publisher.publish(event)
        logger.info("Published UserCreatedEvent for user %s", user.id)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at or datetime.now(timezone.utc),
        )

    async def login(self, dto: LoginDTO) -> TokenResponse:
        identifier = dto.username_or_email
        if "@" in identifier:
            user = await self._repository.find_by_email(identifier)
        else:
            user = await self._repository.find_by_username(identifier)

        if user is None:
            raise InvalidCredentialsException()

        if not self._verify_password(dto.password, user.password_hash):
            raise InvalidCredentialsException()

        access_token = self._create_token(user.id)

        return TokenResponse(
            access_token=access_token,
            user_id=user.id,
            username=user.username,
        )

    async def get_user(self, user_id: int) -> UserResponse:
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise UserNotFoundException(user_id)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at or datetime.now(timezone.utc),
        )
