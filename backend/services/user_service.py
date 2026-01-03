from backend.repositories import get_account_repository, get_user_repository
from typing import Optional, List, Tuple, Dict

from backend.models.mysql.user import User as UserModel
from backend.shared.schemas.user import UserCreate
from ..auth import hash_password, verify_password, create_access_token, Token

# --- CRUD Funktioner ---

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Henter en bruger baseret på ID."""
    repo = get_user_repository()
    return repo.get_by_id(user_id)

def get_user_by_username(username: str) -> Optional[Dict]:
    """Henter en bruger baseret på username."""
    repo = get_user_repository()
    return repo.get_by_username(username)

def get_user_by_email(email: str) -> Optional[Dict]:
    """Henter en bruger baseret på e-mail."""
    repo = get_user_repository()
    return repo.get_by_email(email)

def get_users(skip: int = 0, limit: int = 100) -> List[Dict]:
    """Henter en pagineret liste over brugere."""
    repo = get_user_repository()
    return repo.get_all(skip=skip, limit=limit)

def create_user(user: UserCreate) -> Dict:
    """Opretter en ny bruger og en default account."""
    repo = get_user_repository()
    # Check if email exists
    if repo.get_by_email(user.email):
        raise ValueError("Bruger med denne e-mail eksisterer allerede.")
    
    # Check if username exists
    if repo.get_by_username(user.username):
        raise ValueError("Brugernavn er allerede taget.")
    
    # Hash password
    hashed_password = hash_password(user.password)
    
    # Create user data dictionary
    from datetime import datetime
    user_data = {
        "username": user.username,
        "email": user.email,
        "password": hashed_password,
        "created_at": datetime.utcnow().isoformat()
    }
    
    try:
        # Create user in repository
        created_user = repo.create(user_data)
        
        # Opret automatisk en default account for den nye bruger
        from backend.services import account_service
        from backend.shared.schemas.account import AccountCreate
        default_account = AccountCreate(
            name="Min Konto",
            saldo=0.0,
            User_idUser=created_user["idUser"]
        )
        account_service.create_account(default_account)
        
        return created_user
    except Exception as e:
        # Re-raise the original exception instead of wrapping it
        raise

# --- Authentication Functions ---

def login_user(username_or_email: str, password: str) -> dict:
    """
    Autentificer bruger og returnér JWT token med account_id hvis tilgængelig
    
    Args:
        username_or_email: Username eller email
        password: Plain text password
    
    Returns:
        Dict med Token data og account_id (hvis brugeren har accounts)
    
    Raises:
        ValueError: Hvis login mislykkedes
    """
    # Find bruger by username or email
    user = get_user_repository().authenticate_user(username_or_email)
    
    if not user:
        raise ValueError("Brugernavn eller email ikke fundet.")
    
    # Verify password
    if not verify_password(password, user.password):
        raise ValueError("Forkert adgangskode.")
    
    # Create JWT token
    access_token = create_access_token(
        user_id=user["idUser"],
        username=user["username"],
        email=user["email"]
    )
    
    # Hent første account hvis brugeren har accounts
    account_id = None
    from backend.services import account_service
    accounts = account_service.get_accounts_by_user(user["idUser"])
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

# --- Routeren for User skal opdateres til at bruge disse funktioner ---