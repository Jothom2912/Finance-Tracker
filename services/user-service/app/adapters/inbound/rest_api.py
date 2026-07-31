from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> None:
    if not settings.INTERNAL_API_KEY:
        # P3-59: dette er den ene ende af det tavse account→user-kald.  account-service'
        # `user_adapter.py:26` kollapser alt non-200 til `False`, hvilket bliver en 400
        # "Bruger med dette ID findes ikke" hos slutbrugeren.  En manglende
        # INTERNAL_API_KEY her rapporteres altså som en *valideringsfejl* dér — og indtil
        # nu i tavshed i begge ender.  `error`, ikke `warning`: det er VORES fejl, en
        # deployment uden en påkrævet variabel, ikke noget en caller gjorde.
        logger.error("INTERNAL_API_KEY er ikke sat — internt bruger-opslag afvises med 503")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal user lookup is not configured",
        )
    if not x_internal_api_key or not compare_digest(x_internal_api_key, settings.INTERNAL_API_KEY):
        # De to grene skelnes, fordi de betyder forskellige ting: en manglende header er
        # typisk en fejlkonfigureret *kaldende service* (eller en probe der rammer den
        # interne rute udefra), mens en forkert nøgle er en rotation der kun er nået halvt
        # rundt.  Aldrig hvad der blev sendt — kun at det ikke passede.
        reason = "header mangler" if not x_internal_api_key else "nøglen matcher ikke"
        logger.warning("Internt bruger-opslag afvist: %s", reason)
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
