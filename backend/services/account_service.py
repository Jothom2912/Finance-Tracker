from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from sqlalchemy.exc import IntegrityError

from backend.models.mysql.account import Account as AccountModel
from backend.models.mysql.user import User as UserModel
from backend.shared.schemas.account import AccountCreate, AccountBase

# --- CRUD Funktioner ---

def get_account_by_id(db: Session, account_id: int) -> Optional[AccountModel]:
    """Henter en konto baseret på ID."""
    # Loader User relationship via joinedload for at undgå lazy loading problemer
    return db.query(AccountModel).options(
        joinedload(AccountModel.user)
    ).filter(AccountModel.idAccount == account_id).first()

def get_accounts_by_user(db: Session, user_id: int) -> List[AccountModel]:
    """Henter alle konti tilknyttet en bruger."""
    # Loader User relationship via joinedload for at undgå lazy loading problemer
    return db.query(AccountModel).options(
        joinedload(AccountModel.user)
    ).filter(AccountModel.User_idUser == user_id).all()

def create_account(db: Session, account: AccountCreate) -> AccountModel:
    """Opretter en ny konto og tilknytter den til en bruger."""
    user = db.query(UserModel).filter(UserModel.idUser == account.User_idUser).first()
    if not user:
        raise ValueError("Bruger med dette ID findes ikke.")
        
    db_account = AccountModel(
        name=account.name,
        saldo=account.saldo,
        User_idUser=account.User_idUser
    )
    
    try:
        db.add(db_account)
        db.commit()
        db.refresh(db_account)
        # Reload med user relationship for at sikre korrekt serialisering
        return db.query(AccountModel).options(
            joinedload(AccountModel.user)
        ).filter(AccountModel.idAccount == db_account.idAccount).first()
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved oprettelse af konto.")

def update_account(db: Session, account_id: int, account_data: AccountBase) -> Optional[AccountModel]:
    """Opdaterer saldo og navn på en konto."""
    db_account = get_account_by_id(db, account_id)
    if not db_account:
        return None
        
    db_account.name = account_data.name
    db_account.saldo = account_data.saldo
    
    try:
        db.commit()
        db.refresh(db_account)
        # Reload med user relationship for at sikre korrekt serialisering
        return db.query(AccountModel).options(
            joinedload(AccountModel.user)
        ).filter(AccountModel.idAccount == account_id).first()
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved opdatering af konto.")