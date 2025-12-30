from backend.repositories import get_account_repostitory
from typing import Optional, List

from backend.models.mysql.account import Account as AccountModel
from backend.models.mysql.user import User as UserModel
from backend.shared.schemas.account import AccountCreate, AccountBase

# --- CRUD Funktioner ---

def get_account_by_id(account_id: int) -> Optional[AccountModel]:
    """Henter en konto baseret på ID."""
    repo = get_account_repostitory()
    return repo.get_by_id(account_id)

def get_accounts_by_user(user_id: int) -> List[AccountModel]:
    """Henter alle konti tilknyttet en bruger."""
    repo = get_account_repostitory()
    return repo.get_by_user(user_id)

def create_account( account: AccountCreate) -> AccountModel:
    """Opretter en ny konto og tilknytter den til en bruger."""
    repo = get_account_repostitory()
    new_account = repo.create(account)
    return new_account

def update_account( account_id: int, account_data: AccountBase) -> Optional[AccountModel]:
    """Opdaterer en eksisterende konto baseret på ID."""
    repo= get_account_repostitory()
    return repo.update(account_id, account_data)