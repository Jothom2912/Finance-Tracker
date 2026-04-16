# backend/models/category.py

from .common import Base, Column, Integer, String, budget_category_association, relationship


class Category(Base):
    """Read-only projection of the Category aggregate.

    The source of truth lives in ``transaction-service`` (PostgreSQL).
    Rows here are materialised by ``CategorySyncConsumer`` in response
    to ``category.*`` events.

    **Do not construct this model outside
    ``backend/consumers/category_sync.py``.**  Application services
    should read via ``session.query(Category)`` only.  This invariant
    is enforced by
    ``tests/architecture/test_read_only_projections.py``.
    """

    __tablename__ = "Category"
    __table_args__ = {"info": {"read_only": True, "owned_by": "transaction-service"}}

    idCategory = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False, unique=True, index=True)
    type = Column(String(45), nullable=False)
    display_order = Column(Integer, default=0, nullable=False)

    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", secondary=budget_category_association, back_populates="categories")

    def __repr__(self) -> str:
        return f"<Category(idCategory={self.idCategory}, name='{self.name}')>"
