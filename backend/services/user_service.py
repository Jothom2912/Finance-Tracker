from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from ..models.user import User as UserModel
from ..schemas.user import UserCreate
from ..auth import hash_password, verify_password, create_access_token, Token

# --- CRUD Funktioner ---

def get_user_by_id(db: Session, user_id: int) -> Optional[UserModel]:
    """Henter en bruger baseret på ID."""
    # Bruger `joinedload` for at inkludere relaterede konti og grupper
    return db.query(UserModel).filter(UserModel.idUser == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[UserModel]:
    """Henter en bruger baseret på username."""
    return db.query(UserModel).filter(UserModel.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[UserModel]:
    """Henter en bruger baseret på e-mail."""
    return db.query(UserModel).filter(UserModel.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[UserModel]:
    """Henter en pagineret liste over brugere."""
    return db.query(UserModel).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> UserModel:
    """Opretter en ny bruger."""
    # Check if email exists
    if get_user_by_email(db, user.email):
        raise ValueError("Bruger med denne e-mail eksisterer allerede.")
    
    # Check if username exists
    if get_user_by_username(db, user.username):
        raise ValueError("Brugernavn er allerede taget.")
    
    # Hash password
    hashed_password = hash_password(user.password)
    
    db_user = UserModel(
        username=user.username,
        email=user.email,
        password=hashed_password
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved oprettelse af bruger.")

# --- Authentication Functions ---

def login_user(db: Session, username_or_email: str, password: str) -> Token:
    """
    Autentificer bruger og returnér JWT token
    
    Args:
        db: Database session
        username_or_email: Username eller email
        password: Plain text password
    
    Returns:
        Token object med JWT access token
    
    Raises:
        ValueError: Hvis login mislykkedes
    """
    # Find bruger by username or email
    user = db.query(UserModel).filter(
        or_(
            UserModel.username == username_or_email,
            UserModel.email == username_or_email
        )
    ).first()
    
    if not user:
        raise ValueError("Brugernavn eller email ikke fundet.")
    
    # Verify password
    if not verify_password(password, user.password):
        raise ValueError("Forkert adgangskode.")
    
    # Create JWT token
    access_token = create_access_token(
        user_id=user.idUser,
        username=user.username,
        email=user.email
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.idUser,
        username=user.username,
        email=user.email
    )

# --- Routeren for User skal opdateres til at bruge disse funktioner ---