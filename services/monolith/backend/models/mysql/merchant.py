from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.database.mysql import Base


class Merchant(Base):
    """Learned merchant entity — builds up from transaction data over time."""

    __tablename__ = "Merchant"

    id = Column(Integer, primary_key=True, autoincrement=True)
    normalized_name = Column(String(200), nullable=False, unique=True, index=True)
    display_name = Column(String(200), nullable=False)
    subcategory_id = Column(Integer, ForeignKey("SubCategory.id"), nullable=False)
    transaction_count = Column(Integer, default=0, nullable=False)
    is_user_confirmed = Column(Boolean, default=False, nullable=False)

    subcategory = relationship("SubCategory", backref="merchants")

    def __repr__(self) -> str:
        return f"<Merchant(id={self.id}, name='{self.normalized_name}')>"
