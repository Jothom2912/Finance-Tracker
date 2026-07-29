from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.dto import (
    ChangePasswordDTO,
    ChangeUsernameDTO,
    LoginDTO,
    RegisterDTO,
    TokenResponse,
    UserResponse,
)


class IUserService(ABC):
    """Inbound port defining user use cases."""

    @abstractmethod
    async def register(self, dto: RegisterDTO) -> UserResponse: ...

    @abstractmethod
    async def login(self, dto: LoginDTO) -> TokenResponse: ...

    @abstractmethod
    async def get_user(self, user_id: int) -> UserResponse: ...

    @abstractmethod
    async def change_password(self, user_id: int, dto: ChangePasswordDTO) -> None: ...

    @abstractmethod
    async def change_username(self, user_id: int, dto: ChangeUsernameDTO) -> UserResponse: ...
