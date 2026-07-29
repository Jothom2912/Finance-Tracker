from __future__ import annotations

from hmac import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.application.dto import (
    ChangePasswordDTO,
    ChangeUsernameDTO,
    LoginDTO,
    RegisterDTO,
    TokenResponse,
    UserResponse,
)
from app.application.ports.inbound import IUserService
from app.auth import get_current_user_id
from app.config import settings
from app.dependencies import get_user_service

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> None:
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal user lookup is not configured",
        )
    if not x_internal_api_key or not compare_digest(x_internal_api_key, settings.INTERNAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterDTO,
    service: IUserService = Depends(get_user_service),
) -> UserResponse:
    return await service.register(body)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    body: LoginDTO,
    service: IUserService = Depends(get_user_service),
) -> TokenResponse:
    return await service.login(body)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    user_id: int = Depends(get_current_user_id),
    service: IUserService = Depends(get_user_service),
) -> UserResponse:
    return await service.get_user(user_id)


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def change_my_password(
    body: ChangePasswordDTO,
    user_id: int = Depends(get_current_user_id),
    service: IUserService = Depends(get_user_service),
) -> None:
    await service.change_password(user_id, body)


@router.put(
    "/me/username",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def change_my_username(
    body: ChangeUsernameDTO,
    user_id: int = Depends(get_current_user_id),
    service: IUserService = Depends(get_user_service),
) -> UserResponse:
    return await service.change_username(user_id, body)


# /me-ruterne står FØR /{user_id}. De kolliderer ikke på metode her, men
# rækkefølgen er filens eksisterende regel og skal ikke brydes ved et uheld.
@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_user_by_id(
    user_id: int,
    _: None = Depends(require_internal_api_key),
    service: IUserService = Depends(get_user_service),
) -> UserResponse:
    return await service.get_user(user_id)
