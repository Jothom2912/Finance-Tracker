from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.schemas.user import UserResponse, UserUpdate
from backend.services import user_service
from backend.auth.dependencies import get_current_active_user, get_current_admin_user
from backend.models.user import User

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

@router.get("/", response_model=List[UserResponse])
def read_users_route(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """Henter en liste over brugere (kun admin)."""
    return user_service.get_users(db, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UserResponse)
def read_user_route(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Henter detaljer for en specifik bruger."""
    if current_user.role.value != "admin" and current_user.idUser != user_id:
        raise HTTPException(status_code=403, detail="Ikke tilstrækkelige rettigheder")
    
    db_user = user_service.get_user_by_id(db, user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Bruger ikke fundet")
    return db_user

@router.put("/{user_id}", response_model=UserResponse)
def update_user_route(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Opdater en bruger."""
    if current_user.role.value != "admin" and current_user.idUser != user_id:
        raise HTTPException(status_code=403, detail="Ikke tilstrækkelige rettigheder")
    
    db_user = user_service.update_user(db, user_id, user_update)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Bruger ikke fundet")
    return db_user

@router.delete("/{user_id}")
def delete_user_route(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """Slet en bruger (kun admin)."""
    if current_admin.idUser == user_id:
        raise HTTPException(status_code=400, detail="Du kan ikke slette dig selv")
    
    success = user_service.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bruger ikke fundet")
    return {"message": "Bruger slettet"}