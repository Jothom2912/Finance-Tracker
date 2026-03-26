from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.database.mysql import Base


class SubCategory(Base):
    """Second-level category: Dagligvarer, Restaurant, Offentlig transport, etc."""

    __tablename__ = "SubCategory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("Category.idCategory"), nullable=False)
    is_default = Column(Boolean, default=True, nullable=False)

    category = relationship("Category", backref="subcategories")

    def __repr__(self) -> str:
        return f"<SubCategory(id={self.id}, name='{self.name}')>"
