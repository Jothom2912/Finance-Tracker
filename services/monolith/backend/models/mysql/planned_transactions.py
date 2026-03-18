# backend/models/planned_transactions.py
# Importer fra .common i stedet for .__init__

from .common import DECIMAL, Base, Column, ForeignKey, Integer, String, relationship


class PlannedTransactions(Base):
    """Planlagte transaktioner - Bruges til at planlægge kommende transaktioner"""

    __tablename__ = "PlannedTransactions"

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
