"""
REST API adapter for User bounded context.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.shared.schemas.user import (
    User as UserSchema,
    UserCreate,
    UserLogin,
    TokenResponse,
)
from backend.user.application.service import UserService
from backend.user.domain.exceptions import (
    DuplicateEmail,
    DuplicateUsername,
    UserOrEmailNotFound,
    InvalidCredentials,
)
from backend.auth import get_current_user_id
from backend.dependencies import get_user_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# OPTIONS handlers for CORS preflight
@router.options("/")
def options_users() -> dict:
    """Handle CORS preflight requests."""
    return {"message": "OK"}


@router.options("/{user_id}")
def options_user(user_id: int) -> dict:
    """Handle CORS preflight requests for specific user."""
    return {"message": "OK"}


@router.options("/login")
def options_login() -> dict:
    """Handle CORS preflight requests for login."""
    return {"message": "OK"}


@router.post(
    "/", response_model=UserSchema, status_code=status.HTTP_201_CREATED
)
def create_user(
    user: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserSchema:
    """Opretter en ny bruger."""
    try:
        return service.create_user(user)
    except (DuplicateEmail, DuplicateUsername) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Uventet fejl ved oprettelse af bruger: %s", e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Uventet fejl ved oprettelse af bruger.",
        )


@router.get("/", response_model=list[UserSchema])
def list_users(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends(get_user_service),
    current_user_id: int = Depends(get_current_user_id),
) -> list[UserSchema]:
    """Henter en liste over brugere. Kræver authentication."""
    return service.list_users(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserSchema)
def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    current_user_id: int = Depends(get_current_user_id),
) -> UserSchema:
    """Henter detaljer for en specifik bruger. Kræver authentication."""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Du kan kun se din egen brugerinformation.",
        )

    user = service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bruger ikke fundet.",
        )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    credentials: UserLogin,
    service: UserService = Depends(get_user_service),
) -> dict:
    """Login bruger med username/email og password. Returnér JWT token."""
    try:
        return service.login_user(
            credentials.username_or_email, credentials.password
        )
    except (UserOrEmailNotFound, InvalidCredentials) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )
