# backend/models/category.py

from .common import (
    Base, Column, Integer, String, relationship,
    budget_category_association
)

class Category(Base):
    """Kategori model - Bruges til at kategorisere transaktioner"""
    __tablename__ = "Category"
    
    idCategory = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False, unique=True, index=True)
    type = Column(String(45), nullable=False)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", secondary=budget_category_association, back_populates="categories")
    
    def __repr__(self):
        return f"<Category(idCategory={self.idCategory}, name='{self.name}')>"