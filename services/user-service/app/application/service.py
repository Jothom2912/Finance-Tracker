from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

import anyio.to_thread
from contracts.events.user import UserCreatedEvent
from sqlalchemy.exc import IntegrityError

from app.application.dto import (
    ChangePasswordDTO,
    ChangeUsernameDTO,
    LoginDTO,
    RegisterDTO,
    TokenResponse,
    UserResponse,
)
from app.application.ports.inbound import IUserService
from app.application.ports.outbound import IUnitOfWork
from app.domain.exceptions import (
    CurrentPasswordIncorrectException,
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

            # bcrypt hashing is CPU-bound and ~250ms; offload to a worker
            # thread so it doesn't block the event loop for other requests.
            password_hash = await anyio.to_thread.run_sync(self._hash_password, dto.password)

            try:
                user = await self._uow.users.create(
                    username=dto.username,
                    email=dto.email,
                    password_hash=password_hash,
                )
            except IntegrityError as err:
                # Check-then-insert above has a race window: a concurrent
                # registration can slip in between the uniqueness checks
                # and this insert. The DB-level unique constraint is the
                # real guard; translate its violation into the same 409
                # the pre-checks raise instead of letting it surface as
                # an unhandled 500.
                orig_message = str(err.orig).lower() if err.orig else ""
                if "username" in orig_message:
                    raise UserAlreadyExistsException("username", dto.username) from err
                raise UserAlreadyExistsException("email", dto.email) from err

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

        # Same rationale as register(): bcrypt verification is CPU-bound
        # and ~250ms, so run it off the event loop.
        password_ok = await anyio.to_thread.run_sync(self._verify_password, dto.password, user.password_hash)
        if not password_ok:
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

    async def change_password(self, user_id: int, dto: ChangePasswordDTO) -> None:
        async with self._uow:
            # find_by_id ville ikke duge: den returnerer User uden
            # password_hash, så der ville ikke være noget at verificere mod.
            user = await self._uow.users.find_credentials_by_id(user_id)
            if user is None:
                raise UserNotFoundException(user_id)

            # Samme rationale som register()/login(): bcrypt er CPU-bundet
            # og ~250 ms, så både verifikation og hashing køres af
            # event-loopet.
            current_ok = await anyio.to_thread.run_sync(self._verify_password, dto.current_password, user.password_hash)
            if not current_ok:
                # Bevidst ikke InvalidCredentialsException — den mapper til
                # 401, og frontendens 401-håndtering logger brugeren ud.
                # Se exceptionens docstring.
                raise CurrentPasswordIncorrectException()

            password_hash = await anyio.to_thread.run_sync(self._hash_password, dto.new_password)
            await self._uow.users.update_password(user_id, password_hash)

            await self._uow.commit()

        logger.info("Changed password for user %s", user_id)

    async def change_username(self, user_id: int, dto: ChangeUsernameDTO) -> UserResponse:
        async with self._uow:
            user = await self._uow.users.find_by_id(user_id)
            if user is None:
                raise UserNotFoundException(user_id)

            if user.username == dto.username:
                # No-op: et gem uden ændring skal ikke koste en skrivning,
                # og skal slet ikke ramme unikhedstjekket nedenfor — der
                # ville brugeren kollidere med sig selv og få 409.
                return UserResponse(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    created_at=user.created_at or datetime.now(timezone.utc),
                )

            if await self._uow.users.find_by_username(dto.username):
                raise UserAlreadyExistsException("username", dto.username)

            try:
                updated = await self._uow.users.update_username(user_id, dto.username)
            except IntegrityError as err:
                # Samme check-then-write-race som register(): en samtidig
                # registrering eller omdøbning kan nå navnet mellem tjekket
                # ovenfor og denne skrivning. DB'ens unique-constraint er
                # den rigtige vagt; oversæt til samme 409 frem for en 500.
                raise UserAlreadyExistsException("username", dto.username) from err

            await self._uow.commit()

        logger.info("Changed username for user %s", user_id)

        return UserResponse(
            id=updated.id,
            username=updated.username,
            email=updated.email,
            created_at=updated.created_at or datetime.now(timezone.utc),
        )
