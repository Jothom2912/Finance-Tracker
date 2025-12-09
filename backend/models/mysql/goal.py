# backend/models/goal.py
# Importer fra .common i stedet for .__init__

from .common import (
    Base, Column, Integer, String, DECIMAL, Date, ForeignKey, relationship
)

class Goal(Base):
    """Mål model - Bruges til at sætte sparemål"""
    __tablename__ = "Goal"
    
    idGoal = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=True)
    target_amount = Column(DECIMAL(15, 2), nullable=True)
    current_amount = Column(DECIMAL(15, 2), default=0.00, nullable=True)
    target_date = Column(Date, nullable=True)
    status = Column(String(45), nullable=True)
    Account_idAccount = Column(Integer, ForeignKey("Account.idAccount", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="goals")
    
    def __repr__(self):
        return f"<Goal(idGoal={self.idGoal}, name='{self.name}', status='{self.status}')>"