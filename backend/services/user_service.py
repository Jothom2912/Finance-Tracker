from sqlalchemy.orm import Session, noload
from typing import Optional, List, Tuple, Dict
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from datetime import datetime

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

def create_user(user: UserCreate, db: Session) -> Dict:
    """Opretter en ny bruger og en default account."""
    from backend.repositories import get_user_repository, get_account_repository
    
    repo = get_user_repository(db)
    account_repo = get_account_repository(db)
    
    # Check if email exists
    existing = repo.get_by_email_for_auth(user.email)
    if existing:
        raise ValueError("Bruger med denne e-mail eksisterer allerede.")
    
    # Check if username exists  
    existing = repo.get_by_username_for_auth(user.username)
    if existing:
        raise ValueError("Brugernavn er allerede taget.")
    
    # Hash password
    hashed_password = hash_password(user.password)
    
    # Create user via repository
    user_data = {
        "username": user.username,
        "email": user.email,
        "password": hashed_password,
        "created_at": datetime.now().isoformat()
    }
    
    created_user = repo.create(user_data)
    
    # Opret automatisk en default account
    try:
        account_data = {
            "name": "Min Konto",
            "saldo": 0.0,
            "User_idUser": created_user["idUser"]
        }
        created_account = account_repo.create(account_data)
        print(f"✓ Default account created for user {created_user['idUser']}: account_id={created_account.get('idAccount')}")
    except Exception as e:
        # Log fejl men stop ikke user oprettelse
        print(f"⚠ Warning: Failed to create default account for user {created_user['idUser']}: {e}")
        import traceback
        traceback.print_exc()
        # Optionally: delete the user if account creation fails?
        # For now, we'll continue - user can create account manually
    
    # Returner user uden password
    # Konverter created_at til datetime hvis det er en string
    created_at = created_user.get("created_at")
    if created_at and isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            created_at = datetime.now()
    elif not created_at:
        created_at = datetime.now()
    
    return {
        "idUser": created_user["idUser"],
        "username": created_user["username"],
        "email": created_user["email"],
        "created_at": created_at,
        "accounts": [],  # Tom liste for at matche UserSchema
        "account_groups": []  # Tom liste for at matche UserSchema
    }

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
    from backend.repositories import get_user_repository, get_account_repository
    
    # Hent repository baseret på ACTIVE_DB
    repo = get_user_repository(db)
    
    # Prøv username først
    user = repo.get_by_username_for_auth(username_or_email)
    if not user:
        # Prøv email
        user = repo.get_by_email_for_auth(username_or_email)
    
    if not user:
        raise ValueError("Brugernavn eller email ikke fundet.")
    
    # Verify password
    if not verify_password(password, user["password"]):
        raise ValueError("Forkert adgangskode.")
    
    # Create JWT token
    access_token = create_access_token(
        user_id=user["idUser"],
        username=user["username"],
        email=user["email"]
    )
    
    # Hent første account hvis brugeren har accounts
    account_id = None
    account_repo = get_account_repository(db)
    accounts = account_repo.get_all(user_id=user["idUser"])
    if accounts and len(accounts) > 0:
        account_id = accounts[0]["idAccount"]
    
    # Returner Token data med account_id som dict (så vi kan tilføje account_id)
    result = {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["idUser"],
        "username": user["username"],
        "email": user["email"]
    }
    
    if account_id:
        result['account_id'] = account_id
    
    return result



