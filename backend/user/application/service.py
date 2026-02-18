"""
User Service - Application layer use case implementation.
Orchestrates domain logic and infrastructure through ports.
"""
import logging
from datetime import datetime
from typing import Optional

from backend.user.application.ports.inbound import IUserService
from backend.user.application.ports.outbound import (
    IUserRepository,
    IAccountPort,
)
from backend.user.domain.entities import User
from backend.user.domain.exceptions import (
    DuplicateEmail,
    DuplicateUsername,
    UserOrEmailNotFound,
    InvalidCredentials,
)
from backend.auth import hash_password, verify_password, create_access_token
from backend.shared.schemas.user import (
    UserCreate,
    User as UserSchema,
)

logger = logging.getLogger(__name__)


class UserService(IUserService):
    """
    Application service implementing user use cases.

    Uses constructor injection for all dependencies.
    Auth utilities (hash_password, verify_password, create_access_token)
    are imported directly as they are pure functions.
    """

    def __init__(
        self,
        user_repository: IUserRepository,
        account_port: IAccountPort,
    ):
        self._user_repo = user_repository
        self._account_port = account_port

    # ------------------------------------------------------------------
    # Query use cases
    # ------------------------------------------------------------------

    def get_user(self, user_id: int) -> Optional[UserSchema]:
        """Get a single user by ID."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            return None
        return self._to_dto(user)

    def get_by_username(self, username: str) -> Optional[UserSchema]:
        """Get a user by username."""
        user = self._user_repo.get_by_username(username)
        if not user:
            return None
        return self._to_dto(user)

    def list_users(
        self, skip: int = 0, limit: int = 100
    ) -> list[UserSchema]:
        """List users with pagination."""
        all_users = self._user_repo.get_all()
        return [self._to_dto(u) for u in all_users[skip : skip + limit]]

    # ------------------------------------------------------------------
    # Command use cases
    # ------------------------------------------------------------------

    def create_user(self, data: UserCreate) -> UserSchema:
        """Create a new user and a default account."""
        # Check for duplicate email
        if self._user_repo.get_by_email_for_auth(data.email):
            raise DuplicateEmail(data.email)

        # Check for duplicate username
        if self._user_repo.get_by_username_for_auth(data.username):
            raise DuplicateUsername(data.username)

        # Hash password and create user
        hashed = hash_password(data.password)

        user = User(
            id=None,
            username=data.username,
            email=data.email,
            created_at=datetime.now(),
        )

        created = self._user_repo.create(user, password_hash=hashed)

        # Create default account
        try:
            self._account_port.create_default_account(created.id)
            logger.info(
                "Default account created for user %s", created.id
            )
        except Exception as e:
            logger.warning(
                "Failed to create default account for user %s: %s",
                created.id,
                e,
                exc_info=True,
            )

        return self._to_dto(created)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login_user(self, username_or_email: str, password: str) -> dict:
        """Authenticate user and return JWT token with account_id."""
        # Try username first, then email
        user = self._user_repo.get_by_username_for_auth(username_or_email)
        if not user:
            user = self._user_repo.get_by_email_for_auth(username_or_email)

        if not user:
            raise UserOrEmailNotFound()

        if not verify_password(password, user.password_hash):
            raise InvalidCredentials()

        # Create JWT token
        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            email=user.email,
        )

        result: dict = {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
        }

        # Include first account_id if available
        account_id = self._account_port.get_first_account_id(user.id)
        if account_id:
            result["account_id"] = account_id

        return result

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _to_dto(self, user: User) -> UserSchema:
        return UserSchema(
            idUser=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at or datetime.now(),
            accounts=[],
            account_groups=[],
        )
