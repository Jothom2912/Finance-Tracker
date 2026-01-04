# backend/repositories/mysql/account_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.models.mysql.account import Account as AccountModel
from backend.repositories.base import IAccountRepository

class MySQLAccountRepository(IAccountRepository):
    """MySQL implementation of account repository."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session.
        
        Args:
            db: Database session (required - must be provided via Depends(get_db))
        """
        if db is None:
            raise ValueError("db: Session parameter is required")
        self.db = db
    
    def get_all(self, user_id: Optional[int] = None) -> List[Dict]:
        try:
            query = self.db.query(AccountModel)
            if user_id:
                query = query.filter(AccountModel.User_idUser == user_id)
            accounts = query.all()
            self.db.commit()  # ✅ Commit efter read
            return [self._serialize_account(a) for a in accounts]
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af konti: {e}")
    
    def get_by_id(self, account_id: int) -> Optional[Dict]:
        try:
            account = self.db.query(AccountModel).filter(
                AccountModel.idAccount == account_id
            ).first()
            self.db.commit()  # ✅ Commit efter read
            return self._serialize_account(account) if account else None
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af konto: {e}")
    
    def create(self, account_data: Dict) -> Dict:
        try:
            account = AccountModel(
                name=account_data.get("name"),
                saldo=account_data.get("saldo", 0.0),
                User_idUser=account_data.get("User_idUser")
            )
            self.db.add(account)
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(account)
            return self._serialize_account(account)
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved oprettelse af konto: {e}")
    
    def update(self, account_id: int, account_data: Dict) -> Dict:
        try:
            account = self.db.query(AccountModel).filter(
                AccountModel.idAccount == account_id
            ).first()
            if not account:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                raise ValueError(f"Account {account_id} not found")
            
            if "name" in account_data:
                account.name = account_data["name"]
            if "saldo" in account_data:
                account.saldo = account_data["saldo"]
            
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(account)
            return self._serialize_account(account)
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved opdatering af konto: {e}")
    
    def delete(self, account_id: int) -> bool:
        try:
            account = self.db.query(AccountModel).filter(
                AccountModel.idAccount == account_id
            ).first()
            if not account:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                return False
            
            self.db.delete(account)
            self.db.commit()  # ✅ Commit efter write
            return True
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved sletning af konto: {e}")
    
    @staticmethod
    def _serialize_account(account: AccountModel) -> Dict:
        return {
            "idAccount": account.idAccount,
            "name": account.name,
            "saldo": float(account.saldo) if account.saldo else 0.0,
            "User_idUser": account.User_idUser
        }

