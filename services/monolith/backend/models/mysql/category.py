# backend/models/category.py

from .common import Base, Column, Integer, String, budget_category_association, relationship


class Category(Base):
    """Top-level category: Mad & drikke, Bolig, Transport, etc."""

    __tablename__ = "Category"

    idCategory = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False, unique=True, index=True)
    type = Column(String(45), nullable=False)
    display_order = Column(Integer, default=0, nullable=False)

    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", secondary=budget_category_association, back_populates="categories")

    def __repr__(self) -> str:
        return f"<Category(idCategory={self.idCategory}, name='{self.name}')>"
