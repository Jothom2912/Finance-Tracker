from sqlalchemy.orm import Session, noload
from typing import Optional, List, Tuple
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from backend.models.mysql.user import User as UserModel
from backend.shared.schemas.user import UserCreate
from ..auth import hash_password, verify_password, create_access_token, Token

# --- CRUD Funktioner ---

def get_user_by_id(db: Session, user_id: int) -> Optional[UserModel]:
    """Henter en bruger baseret på ID."""
    # Brug noload for at undgå at loade relationships (forbedrer performance)
    return db.query(UserModel).options(
        noload(UserModel.accounts),
        noload(UserModel.account_groups)
    ).filter(UserModel.idUser == user_id).first()

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
    """Opretter en ny bruger og en default account."""
    # Check if email exists
    if get_user_by_email(db, user.email):
        raise ValueError("Bruger med denne e-mail eksisterer allerede.")
    
    # Check if username exists
    if get_user_by_username(db, user.username):
        raise ValueError("Brugernavn er allerede taget.")
    
    # Hash password
    hashed_password = hash_password(user.password)
    
    # Create user
    db_user = UserModel(
        username=user.username,
        email=user.email,
        password=hashed_password
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Opret automatisk en default account for den nye bruger
        from backend.models.mysql.account import Account as AccountModel
        default_account = AccountModel(
            name="Min Konto",
            saldo=0.0,
            User_idUser=db_user.idUser
        )
        db.add(default_account)
        db.commit()
        
        # Reload user med noload options for at undgå lazy loading problemer
        user_id = db_user.idUser
        db_user = db.query(UserModel).options(
            noload(UserModel.accounts),
            noload(UserModel.account_groups)
        ).filter(UserModel.idUser == user_id).first()
        
        # Sæt relationships til tomme lister for at undgå lazy loading ved serialisering
        if db_user:
            db_user.accounts = []
            db_user.account_groups = []
        
        return db_user
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved oprettelse af bruger.")
    except Exception as e:
        db.rollback()
        # Re-raise the original exception instead of wrapping it
        raise

# --- Authentication Functions ---

def login_user(db: Session, username_or_email: str, password: str) -> dict:
    """
    Autentificer bruger og returnér JWT token med account_id hvis tilgængelig
    
    Args:
        db: Database session
        username_or_email: Username eller email
        password: Plain text password
    
    Returns:
        Dict med Token data og account_id (hvis brugeren har accounts)
    
    Raises:
        ValueError: Hvis login mislykkedes
    """
    # Find bruger by username or email
    # Brug .options() for at undgå at loade relationships (accounts, account_groups)
    user = db.query(UserModel).options(
        noload(UserModel.accounts),
        noload(UserModel.account_groups)
    ).filter(
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
    
    # Hent første account hvis brugeren har accounts
    account_id = None
    from backend.services import account_service
    accounts = account_service.get_accounts_by_user(db, user.idUser)
    if accounts and len(accounts) > 0:
        account_id = accounts[0].idAccount
    
    # Returner Token data med account_id som dict (så vi kan tilføje account_id)
    result = {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.idUser,
        "username": user.username,
        "email": user.email
    }
    
    if account_id:
        result['account_id'] = account_id
    
    return result

# --- Routeren for User skal opdateres til at bruge disse funktioner ---