# backend/models/planned_transactions.py
# Importer fra .common i stedet for .__init__

from .common import DECIMAL, Base, Column, ForeignKey, Integer, String, relationship


class PlannedTransactions(Base):
    """Read-only projection of the PlannedTransaction aggregate.

    The source of truth lives in ``transaction-service`` (PostgreSQL).
    Planned-transaction events aren't routed to a projection consumer
    yet (they were extracted with the transaction bounded context in
    milestone 2), so this table currently contains only historical
    rows.

    **Do not construct this model in application code.**  Writes to
    planned transactions belong in ``transaction-service`` via
    ``POST /api/v1/planned-transactions/``.  Enforced by
    ``tests/architecture/test_read_only_projections.py``.
    """

    __tablename__ = "PlannedTransactions"
    __table_args__ = {"info": {"read_only": True, "owned_by": "transaction-service"}}

    idPlannedTransactions = Column(Integer, primary_key=True, autoincrement=True)
    Transaction_idTransaction = Column(
        Integer, ForeignKey("Transaction.idTransaction", ondelete="SET NULL"), nullable=True
    )
    name = Column(String(45), nullable=True)
    amount = Column(DECIMAL(15, 2), nullable=True)

    # Relationships
    transaction = relationship("Transaction", back_populates="planned_transaction")

    def __repr__(self):
        return f"<PlannedTransactions(idPlannedTransactions={self.idPlannedTransactions}, name='{self.name}')>"
