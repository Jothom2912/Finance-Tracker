from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy.exc import IntegrityError

from backend.models.mysql.account_groups import AccountGroups as AGModel
from backend.models.mysql.user import User as UserModel
from backend.shared.schemas.account_groups import AccountGroupsCreate, AccountGroupsBase

# --- CRUD Funktioner ---

def get_group_by_id(db: Session, group_id: int) -> Optional[AGModel]:
    """Henter en kontogruppe baseret på ID."""
    return db.query(AGModel).filter(AGModel.idAccountGroups == group_id).first()

def get_groups(db: Session, skip: int = 0, limit: int = 100) -> List[AGModel]:
    """Henter en pagineret liste over kontogrupper."""
    return db.query(AGModel).offset(skip).limit(limit).all()

def create_group(db: Session, group_data: AccountGroupsCreate) -> AGModel:
    """Opretter en ny kontogruppe og tilknytter brugere."""
    
    user_ids = group_data.user_ids
    group_info = group_data.model_dump(exclude={"user_ids"})

    db_group = AGModel(**group_info)
    
    # Tilknyt brugere
    users = db.query(UserModel).filter(UserModel.idUser.in_(user_ids)).all()
    if len(users) != len(user_ids):
        # Dette indikerer, at mindst én bruger-ID er ugyldig
        raise ValueError("Mindst én bruger ID er ugyldig.")
        
    db_group.users.extend(users)
    
    try:
        db.add(db_group)
        db.commit()
        db.refresh(db_group)
        return db_group
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved oprettelse af gruppe.")

def update_group(db: Session, group_id: int, group_data: AccountGroupsCreate) -> Optional[AGModel]:
    """Opdaterer en kontogruppe (inkl. dens tilknyttede brugere)."""
    db_group = get_group_by_id(db, group_id)
    if not db_group:
        return None

    update_data = group_data.model_dump(exclude_unset=True)
    
    if 'user_ids' in update_data:
        new_user_ids = update_data.pop('user_ids')
        users = db.query(UserModel).filter(UserModel.idUser.in_(new_user_ids)).all()
        if len(users) != len(new_user_ids):
            raise ValueError("Mindst én ny bruger ID er ugyldig.")
        # Erstat de eksisterende brugere
        db_group.users = users 

    # Opdater de øvrige felter
    for key, value in update_data.items():
        setattr(db_group, key, value)
    
    try:
        db.commit()
        db.refresh(db_group)
        return db_group
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved opdatering af gruppe.")