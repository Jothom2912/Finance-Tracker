from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from backend.repositories import get_account_repository, get_user_repository
from backend.shared.schemas.account import AccountCreate, AccountBase

# --- CRUD Funktioner ---

def get_account_by_id(account_id: int, db: Session) -> Optional[Dict]:
    """Henter en konto baseret på ID."""
    repo = get_account_repository(db)
    return repo.get_by_id(account_id)

def get_accounts_by_user(user_id: int, db: Session) -> List[Dict]:
    """Henter alle konti tilknyttet en bruger."""
    repo = get_account_repository(db)
    return repo.get_all(user_id=user_id)

def create_account(account: AccountCreate, db: Session) -> Dict:
    """Opretter en ny konto og tilknytter den til en bruger."""
    user_repo = get_user_repository(db)
    user = user_repo.get_by_id(account.User_idUser)
    if not user:
        raise ValueError("Bruger med dette ID findes ikke.")
        
    repo = get_account_repository(db)
    account_data = {
        "name": account.name,
        "saldo": account.saldo,
        "User_idUser": account.User_idUser
    }
    
    try:
        return repo.create(account_data)
    except Exception as e:
        raise ValueError(f"Integritetsfejl ved oprettelse af konto: {str(e)}")

def update_account(account_id: int, account_data: AccountBase, db: Session) -> Optional[Dict]:
    """Opdaterer saldo og navn på en konto."""
    repo = get_account_repository(db)
    existing = repo.get_by_id(account_id)
    if not existing:
        return None
        
    update_data = {
        "name": account_data.name,
        "saldo": account_data.saldo
    }
    
    try:
        return repo.update(account_id, update_data)
    except Exception as e:
        raise ValueError(f"Integritetsfejl ved opdatering af konto: {str(e)}")
