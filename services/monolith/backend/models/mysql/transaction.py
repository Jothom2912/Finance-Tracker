# backend/models/transaction.py
# Importér fra .common i stedet for .__init__

from .common import DECIMAL, Base, Column, DateTime, ForeignKey, Integer, String, func, relationship


class Transaction(Base):
    """Read-only projection of the Transaction aggregate.

    The source of truth lives in ``transaction-service`` (PostgreSQL).
    This MySQL row is materialised by ``TransactionSyncConsumer`` in
    response to ``transaction.*`` events from the bus.

    **Do not construct this model outside
    ``backend/consumers/transaction_sync.py``.**  Writes from
    application services would create a split-brain with the owning
    service; reads via ``session.query(Transaction)`` are fine.  This
    invariant is enforced by
    ``tests/architecture/test_read_only_projections.py``.
    """

    __tablename__ = "Transaction"
    __table_args__ = {"info": {"read_only": True, "owned_by": "transaction-service"}}

    idTransaction = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(DECIMAL(15, 2), nullable=False)
    description = Column(String(255), nullable=True, index=True)
    date = Column(DateTime, default=func.now(), nullable=False)
    type = Column(String(45), nullable=False)  # 'income' eller 'expense'
    Category_idCategory = Column(Integer, ForeignKey("Category.idCategory"), nullable=True)
    Account_idAccount = Column(Integer, ForeignKey("Account.idAccount", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False, server_default=func.now())

    # New categorization hierarchy fields (nullable during transition)
    subcategory_id = Column(Integer, ForeignKey("SubCategory.id"), nullable=True)
    merchant_id = Column(Integer, ForeignKey("Merchant.id"), nullable=True)
    categorization_tier = Column(String(20), nullable=True)
    categorization_confidence = Column(String(10), nullable=True)

    category = relationship("Category", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    planned_transaction = relationship("PlannedTransactions", back_populates="transaction", uselist=False)
    subcategory = relationship("SubCategory", backref="transactions")
    merchant = relationship("Merchant", backref="transactions")

    def __repr__(self) -> str:
        return f"<Transaction(idTransaction={self.idTransaction}, amount={self.amount}, type='{self.type}')>"
