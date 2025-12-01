from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from backend.database import get_db
from backend.auth.dependencies import get_current_active_user, get_current_admin_user
from backend.auth.security import create_access_token, get_password_hash, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES
from backend.schemas.user import UserCreate, UserResponse, Token
from backend.models.user import User, UserRole  # Importer direkte fra user.py

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Registrer en ny bruger."""
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Brugernavn er allerede registreret")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email er allerede registreret")
    
    db_user = User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password),
        role=UserRole.USER
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login og få access token."""
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Forkert brugernavn eller password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Bruger er deaktiveret")
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value, "user_id": user.idUser},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Hent nuværende brugeroplysninger."""
    return current_user

@router.post("/create-admin", response_model=UserResponse)
def create_admin(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """Opret en ny admin bruger (kun admin)."""
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Brugernavn er allerede registreret")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email er allerede registreret")
    
    db_user = User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password),
        role=UserRole.ADMIN
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user