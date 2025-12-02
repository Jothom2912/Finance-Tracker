# backend/models/user.py

from .common import (
    Base, Column, Integer, String, DateTime, func, relationship,
    account_group_user_association 
)

class User(Base):
    """Bruger model - Håndterer autentifikation og brugeroplysninger"""
    __tablename__ = "User"
    
    idUser = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(45), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)  # Hashed password
    email = Column(String(45), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    account_groups = relationship("AccountGroups", secondary=account_group_user_association, back_populates="users")
    
    def __repr__(self):
        return f"<User(idUser={self.idUser}, username='{self.username}')>"