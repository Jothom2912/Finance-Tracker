from backend.repositories import get_account_group_repository
from typing import Optional, List, Dict

from backend.repositories.mysql.groupAccount_repository import MySQGroupAccountRepository
from backend.repositories.base import IGroupAccountRepository
from backend.models.mysql.account_groups import AccountGroups as AGModel
from backend.models.mysql.user import User as UserModel
from backend.shared.schemas.account_groups import AccountGroupsCreate, AccountGroupsBase

# --- CRUD Funktioner ---

def get_group_by_id(group_id: int) -> Optional[dict]:
    """Henter en kontogruppe baseret på ID."""
    repo=  get_account_group_repository()
    data = repo.get_by_id(group_id)
    return data

def get_groups() -> List[dict]:
    """Henter en pagineret liste over kontogrupper."""
    repo: IGroupAccountRepository = get_account_group_repository()
    all_groups = repo.get_all()
    return all_groups

def create_group( group_data: AccountGroupsCreate) -> dict:
    """Opretter en ny kontogruppe og tilknytter brugere."""
    
    user_ids = group_data.user_ids
    group_info = group_data.model_dump(exclude={"user_ids"})

    repo: IGroupAccountRepository = get_account_group_repository()
    result = repo.create(group_info)
    group_id = result['idAccountGroups']
    
    # Get the created group from db to add users
    db_group = db.query(AGModel).filter(AGModel.idAccountGroups == group_id).first()
    
    # Tilknyt brugere
    users = db.query(UserModel).filter(UserModel.idUser.in_(user_ids)).all()
    if len(users) != len(user_ids):
        # Dette indikerer, at mindst én bruger-ID er ugyldig
        raise ValueError("Mindst én bruger ID er ugyldig.")
        
    db_group.users.extend(users)

    return db_group

def update_group(group_id: int, group_data: AccountGroupsCreate) -> Optional[dict]:
    """Opdaterer en kontogruppe (inkl. dens tilknyttede brugere)."""
    repo: IGroupAccountRepository = get_account_group_repository()
    
    update_data = group_data.model_dump(exclude_unset=True)

    # Update the basic fields using repo
    if update_data:
        repo.update(group_id, update_data)
    
    # Refresh and return
    return update_data

def delete_group( group_id: int) -> bool:
    """Sletter en kontogruppe."""
    repo= get_account_group_repository()
    return repo.delete(group_id)