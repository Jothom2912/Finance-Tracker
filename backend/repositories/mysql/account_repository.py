# backend/repositories/mysql/account_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.database.mysql import SessionLocal
from backend.models.mysql.account import Account as AccountModel
from backend.repositories.base import IAccountRepository

class MySQLAccountRepository(IAccountRepository):
    """MySQL implementation of account repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(self, user_id: Optional[int] = None) -> List[Dict]:
        query = self.db.query(AccountModel)
        if user_id:
            query = query.filter(AccountModel.User_idUser == user_id)
        accounts = query.all()
        return [self._serialize_account(a) for a in accounts]
    
    def get_by_id(self, account_id: int) -> Optional[Dict]:
        account = self.db.query(AccountModel).filter(
            AccountModel.idAccount == account_id
        ).first()
        return self._serialize_account(account) if account else None
    
    def create(self, account_data: Dict) -> Dict:
        account = AccountModel(
            name=account_data.get("name"),
            saldo=account_data.get("saldo", 0.0),
            User_idUser=account_data.get("User_idUser")
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return self._serialize_account(account)
    
    def update(self, account_id: int, account_data: Dict) -> Dict:
        account = self.db.query(AccountModel).filter(
            AccountModel.idAccount == account_id
        ).first()
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        if "name" in account_data:
            account.name = account_data["name"]
        if "saldo" in account_data:
            account.saldo = account_data["saldo"]
        
        self.db.commit()
        self.db.refresh(account)
        return self._serialize_account(account)
    
    def delete(self, account_id: int) -> bool:
        account = self.db.query(AccountModel).filter(
            AccountModel.idAccount == account_id
        ).first()
        if not account:
            return False
        self.db.delete(account)
        self.db.commit()
        return True
    
    @staticmethod
    def _serialize_account(account: AccountModel) -> Dict:
        return {
            "idAccount": account.idAccount,
            "name": account.name,
            "saldo": float(account.saldo) if account.saldo else 0.0,
            "User_idUser": account.User_idUser
        }

