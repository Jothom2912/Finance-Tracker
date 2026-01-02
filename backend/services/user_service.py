from backend.repositories import get_account_repository, get_user_repository
from typing import Optional, List, Tuple

from backend.models.mysql.user import User as UserModel
from backend.shared.schemas.user import UserCreate
from ..auth import hash_password, verify_password, create_access_token, Token

# --- CRUD Funktioner ---

def get_user_by_id(user_id: int) -> Optional[UserModel]:
    """Henter en bruger baseret på ID."""
    # Brug noload for at undgå at loade relationships (forbedrer performance)
    repo= get_user_repository()
    return repo.get_by_id(user_id)

def get_user_by_username(username: str) -> Optional[UserModel]:
    """Henter en bruger baseret på username."""
    repo= get_user_repository()
    return repo.get_by_username(username)

def get_user_by_email(email: str) -> Optional[UserModel]:
    """Henter en bruger baseret på e-mail."""
    repo= get_user_repository()
    return repo.get_by_email(email)

def get_users(skip: int = 0, limit: int = 100) -> List[UserModel]:
    """Henter en pagineret liste over brugere."""
    repo= get_user_repository()
    return repo.get_all(skip=skip, limit=limit)

def create_user(user: UserCreate) -> UserModel:
    """Opretter en ny bruger og en default account."""
    repo= get_user_repository()
    # Check if email exists
    if repo.get_user_by_email(user.email):
        raise ValueError("Bruger med denne e-mail eksisterer allerede.")
    
    # Check if username exists
    if repo.get_user_by_username(user.username):
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
        repo.create(db_user)
        
        # Opret automatisk en default account for den nye bruger
        from backend.models.mysql.account import Account as AccountModel
        repo= get_account_repository()
        default_account = AccountModel(
            name="Min Konto",
            saldo=0.0,
            User_idUser=db_user.idUser
        )
        repo.create(default_account)
        
        # Reload user med noload options for at undgå lazy loading problemer
        user_id = db_user.idUser
        db_user = get_user_repository().get_by_id(user_id)
        
        # Sæt relationships til tomme lister for at undgå lazy loading ved serialisering
        if db_user:
            db_user.accounts = []
            db_user.account_groups = []
        
        return db_user
    except Exception as e:
        # Re-raise the original exception instead of wrapping it
        raise

# --- Authentication Functions ---

def login_user( username_or_email: str, password: str) -> dict:
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