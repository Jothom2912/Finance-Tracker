# backend/repositories/mysql/user_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.database.mysql import SessionLocal
from backend.models.mysql.user import User as UserModel
from backend.repositories.base import IUserRepository

class MySQLUserRepository(IUserRepository):
    """MySQL implementation of user repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(self) -> List[Dict]:
        users = self.db.query(UserModel).all()
        return [self._serialize_user(u) for u in users]
    
    def get_by_id(self, user_id: int) -> Optional[Dict]:
        user = self.db.query(UserModel).filter(UserModel.idUser == user_id).first()
        return self._serialize_user(user) if user else None
    
    def get_by_username(self, username: str) -> Optional[Dict]:
        user = self.db.query(UserModel).filter(UserModel.username == username).first()
        return self._serialize_user(user) if user else None
    
    def get_by_email(self, email: str) -> Optional[Dict]:
        user = self.db.query(UserModel).filter(UserModel.email == email).first()
        return self._serialize_user(user) if user else None
    
    def create(self, user_data: Dict) -> Dict:
        user = UserModel(
            username=user_data.get("username"),
            email=user_data.get("email"),
            password=user_data.get("password")
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return self._serialize_user(user)
    
    def authenticate_user(self, username_or_email: str) -> Optional[Dict]:
        """Get user data including password for authentication."""
        user = self.db.query(UserModel).filter(
            (UserModel.username == username_or_email) | (UserModel.email == username_or_email)
        ).first()
        if user:
            return {
                "idUser": user.idUser,
                "username": user.username,
                "email": user.email,
                "password": user.password,  # Include password for authentication
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
        return None
    
    @staticmethod
    def _serialize_user(user: UserModel) -> Dict:
        return {
            "idUser": user.idUser,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None
            # IKKE inkluder password!
        }

