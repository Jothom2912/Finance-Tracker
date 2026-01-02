from backend.repositories import get_account_repository
from typing import Optional, List

from backend.shared.schemas.account import AccountCreate, AccountBase

# --- CRUD Funktioner ---

def get_account_by_id(account_id: int) -> Optional[dict]:
    """Henter en konto baseret på ID."""
    repo = get_account_repository()
    return repo.get_by_id(account_id)

def get_accounts_by_user(user_id: int) -> List[dict]:
    """Henter alle konti tilknyttet en bruger."""
    repo = get_account_repository()
    return repo.get_all(user_id=user_id)

def create_account( account: AccountCreate) -> dict:
    """Opretter en ny konto og tilknytter den til en bruger."""
    repo = get_account_repository()
    new_account = repo.create(account)
    return new_account

def update_account( account_id: int, account_data: AccountBase) -> Optional[dict]:
    """Opdaterer en eksisterende konto baseret på ID."""
    repo= get_account_repository()
    return repo.update(account_id, account_data)