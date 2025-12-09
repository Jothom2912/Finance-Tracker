# backend/models/budget.py

from .common import (
    Base, 
    Column, 
    Integer, 
    DECIMAL, 
    Date, 
    ForeignKey, 
    relationship,
    # IMPORTER NU ASSOCIATIONSTABELLEN DIREKTE FRA COMMON.PY:
    budget_category_association
)
# FJERN DEN GAMLE LINJE:
# from .__init__ import budget_category_association

class Budget(Base):
    """Budget model - Bruges til at sætte budgetter per kategori"""
    __tablename__ = "Budget"
    
    idBudget = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(DECIMAL(15, 2), nullable=False)
    budget_date = Column(Date, nullable=True)
    Account_idAccount = Column(Integer, ForeignKey("Account.idAccount", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="budgets")
    categories = relationship("Category", secondary=budget_category_association, back_populates="budgets")
    
    def __repr__(self):
        return f"<Budget(idBudget={self.idBudget}, amount={self.amount})>"