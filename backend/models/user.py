# backend/models/user.py

from .common import (
    Base, Column, Integer, String, DateTime, func, relationship,
    account_group_user_association 
)
from sqlalchemy import Enum
import enum

class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"

class User(Base):
    """Bruger model - Håndterer autentifikation og brugeroplysninger"""
    __tablename__ = "User"
    
    idUser = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(20), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)
    email = Column(String(100), nullable=False, unique=True, index=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    account_groups = relationship("AccountGroups", secondary=account_group_user_association, back_populates="users")
    
    def __repr__(self):
        return f"<User(idUser={self.idUser}, username='{self.username}', role='{self.role.value}')>"