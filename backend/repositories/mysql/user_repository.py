# backend/repositories/mysql/user_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.models.mysql.user import User as UserModel
from backend.repositories.base import IUserRepository

class MySQLUserRepository(IUserRepository):
    """MySQL implementation of user repository."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session.
        
        Args:
            db: Database session (required - must be provided via Depends(get_db))
        """
        if db is None:
            raise ValueError("db: Session parameter is required")
        self.db = db
    
    def get_all(self) -> List[Dict]:
        try:
            users = self.db.query(UserModel).all()
            return [self._serialize_user(u) for u in users]
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af brugere: {e}")
    
    def get_by_id(self, user_id: int) -> Optional[Dict]:
        try:
            user = self.db.query(UserModel).filter(UserModel.idUser == user_id).first()
            return self._serialize_user(user) if user else None
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af bruger: {e}")
    
    def get_by_username(self, username: str) -> Optional[Dict]:
        try:
            user = self.db.query(UserModel).filter(UserModel.username == username).first()
            return self._serialize_user(user) if user else None
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af bruger: {e}")
    
    def create(self, user_data: Dict) -> Dict:
        try:
            user = UserModel(
                username=user_data.get("username"),
                email=user_data.get("email"),
                password=user_data.get("password")
            )
            self.db.add(user)
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(user)
            return self._serialize_user(user)
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved oprettelse af bruger: {e}")
    
    def get_by_username_for_auth(self, username: str) -> Optional[Dict]:
        """Get user by username INCLUDING password - kun til authentication."""
        try:
            user = self.db.query(UserModel).filter(UserModel.username == username).first()
            if user:
                return {
                    "idUser": user.idUser,
                    "username": user.username,
                    "email": user.email,
                    "password": user.password,  # Inkluder password
                    "created_at": user.created_at.isoformat() if user.created_at else None
                }
            return None
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af bruger til auth: {e}")
    
    def get_by_email_for_auth(self, email: str) -> Optional[Dict]:
        """Get user by email INCLUDING password - kun til authentication."""
        try:
            user = self.db.query(UserModel).filter(UserModel.email == email).first()
            if user:
                return {
                    "idUser": user.idUser,
                    "username": user.username,
                    "email": user.email,
                    "password": user.password,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                }
            return None
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af bruger til auth: {e}")
    
    @staticmethod
    def _serialize_user(user: UserModel) -> Dict:
        return {
            "idUser": user.idUser,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None
            # IKKE inkluder password!
        }

