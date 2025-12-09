# backend/models/account.py

# Importér fra det fælles .common modul for at få adgang til Base, Column, osv.
from .common import (
    Base, Column, Integer, String, DECIMAL, ForeignKey, relationship
)

class Account(Base):
    """Konto model - Bruger kan have flere konti"""
    __tablename__ = "Account"
    
    idAccount = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False)
    saldo = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    User_idUser = Column(Integer, ForeignKey("User.idUser", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="account", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Account(idAccount={self.idAccount}, name='{self.name}', saldo={self.saldo})>"