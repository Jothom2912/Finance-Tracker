from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.dto import ExistsResponse, LoginDTO, RegisterDTO, TokenResponse, UserResponse
from app.application.ports.inbound import IUserService
from app.auth import get_current_user_id
from app.dependencies import get_user_service

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


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


@router.get(
    "/{user_id}/exists",
    response_model=ExistsResponse,
    status_code=status.HTTP_200_OK,
)
async def user_exists(
    user_id: int,
    service: IUserService = Depends(get_user_service),
) -> ExistsResponse:
    exists = await service.user_exists(user_id)
    return ExistsResponse(exists=exists)
