from backend.repositories import get_account_group_repository
from typing import Optional, List, Dict

from backend.repositories.mysql.groupAccount_repository import MySQGroupAccountRepository
from backend.repositories.base import IGroupAccountRepository
from backend.shared.schemas.account_groups import AccountGroupsCreate, AccountGroupsBase

# --- CRUD Funktioner ---

def get_group_by_id(group_id: int) -> Optional[dict]:
    """Henter en kontogruppe baseret på ID."""
    repo=  get_account_group_repository()
    data = repo.get_by_id(group_id)
    return data

def get_groups(skip: int = 0, limit: int = 100) -> List[dict]:
    """Henter en pagineret liste over kontogrupper."""
    repo: IGroupAccountRepository = get_account_group_repository()
    all_groups = repo.get_all()
    # Apply pagination
    return all_groups[skip:skip + limit]

def create_group( group_data: AccountGroupsCreate) -> dict:
    """Opretter en ny kontogruppe og tilknytter brugere."""
    
    user_ids = group_data.user_ids
    group_info = group_data.model_dump(exclude={"user_ids"})
    
    # Include user_ids in group_info for repository to handle association
    group_info["user_ids"] = user_ids

    repo: IGroupAccountRepository = get_account_group_repository()
    result = repo.create(group_info)
    
    return result

def update_group(group_id: int, group_data: AccountGroupsCreate) -> Optional[dict]:
    """Opdaterer en kontogruppe (inkl. dens tilknyttede brugere)."""
    repo: IGroupAccountRepository = get_account_group_repository()
    
    update_data = group_data.model_dump(exclude_unset=True)

    # Update the basic fields using repo
    if update_data:
        result = repo.update(group_id, update_data)
        return result
    
    # If no updates, return current data
    return repo.get_by_id(group_id)

def delete_group( group_id: int) -> bool:
    """Sletter en kontogruppe."""
    repo= get_account_group_repository()
    return repo.delete(group_id)