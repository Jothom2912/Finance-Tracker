from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy.exc import IntegrityError

from ..models.user import User as UserModel
from ..schemas.user import UserCreate

# --- CRUD Funktioner ---

def get_user_by_id(db: Session, user_id: int) -> Optional[UserModel]:
    """Henter en bruger baseret på ID."""
    # Bruger `joinedload` for at inkludere relaterede konti og grupper
    return db.query(UserModel).filter(UserModel.idUser == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[UserModel]:
    """Henter en bruger baseret på e-mail."""
    return db.query(UserModel).filter(UserModel.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[UserModel]:
    """Henter en pagineret liste over brugere."""
    return db.query(UserModel).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> UserModel:
    """Opretter en ny bruger."""
    if get_user_by_email(db, user.email):
        raise ValueError("Bruger med denne e-mail eksisterer allerede.")
    
    # Bemærk: Her ville du typisk hashe kodeordet før gemning
    # hashed_password = hash_password(user.password) 
    
    db_user = UserModel(
        username=user.username,
        email=user.email,
        # I en rigtig app ville dette være det hashede kodeord
        hashed_password=user.password 
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved oprettelse af bruger.")

# --- Routeren for User skal opdateres til at bruge disse funktioner ---