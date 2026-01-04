# backend/models/transaction.py
# Importér fra .common i stedet for .__init__

from .common import (
    Base, Column, Integer, DECIMAL, String, DateTime, func, ForeignKey, relationship
)

class Transaction(Base):
    """Transaktion model - Registrerer ind- og udgifter"""
    __tablename__ = "Transaction"
    
    idTransaction = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(DECIMAL(15, 2), nullable=False)
    description = Column(String(255), nullable=True, index=True)
    date = Column(DateTime, default=func.now(), nullable=False)
    type = Column(String(45), nullable=False) # 'income' eller 'expense'
    Category_idCategory = Column(Integer, ForeignKey("Category.idCategory"), nullable=False)
    Account_idAccount = Column(Integer, ForeignKey("Account.idAccount", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False, server_default=func.now())
    
    # Relationships
    category = relationship("Category", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    planned_transaction = relationship("PlannedTransactions", back_populates="transaction", uselist=False)
    
    def __repr__(self):
        return f"<Transaction(idTransaction={self.idTransaction}, amount={self.amount}, type='{self.type}')>"