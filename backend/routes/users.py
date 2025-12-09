from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.shared.schemas.user import User as UserSchema, UserCreate, UserLogin, TokenResponse
from backend.services import user_service
from backend.auth import get_current_user_id

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

# OPTIONS handler for CORS preflight
@router.options("/")
def options_users():
    """Handle CORS preflight requests"""
    return {"message": "OK"}

@router.options("/{user_id}")
def options_user(user_id: int):
    """Handle CORS preflight requests for specific user"""
    return {"message": "OK"}

@router.options("/login")
def options_login():
    """Handle CORS preflight requests for login"""
    return {"message": "OK"}

@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user_route(user: UserCreate, db: Session = Depends(get_db)):
    """Opretter en ny bruger."""
    try:
        db_user = user_service.create_user(db, user)
        return db_user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Uventet fejl ved oprettelse af bruger: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Uventet fejl ved oprettelse af bruger."
        )

@router.get("/", response_model=List[UserSchema])
def read_users_route(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Henter en liste over brugere. Kræver authentication."""
    # Kun admin bør kunne se alle brugere, men for nu tillader vi authenticated users
    return user_service.get_users(db, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UserSchema)
def read_user_route(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Henter detaljer for en specifik bruger. Kræver authentication."""
    # Kun tillad at se sin egen bruger eller admin
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Du kan kun se din egen brugerinformation."
        )
    
    db_user = user_service.get_user_by_id(db, user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bruger ikke fundet.")
    return db_user

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login_route(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login bruger med username/email og password. Returnér JWT token."""
    try:
        token = user_service.login_user(db, credentials.username_or_email, credentials.password)
        return token
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))