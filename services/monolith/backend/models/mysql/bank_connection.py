from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from backend.database.mysql import Base


class BankConnection(Base):
    """Stores Enable Banking session data for a connected bank account."""

    __tablename__ = "BankConnection"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("Account.idAccount"), nullable=False)
    session_id = Column(String(200), nullable=False, index=True)
    bank_name = Column(String(100), nullable=False)
    bank_country = Column(String(5), nullable=False, default="DK")
    bank_account_uid = Column(String(200), nullable=False)
    bank_account_iban = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    expires_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<BankConnection(id={self.id}, bank='{self.bank_name}', status='{self.status}')>"
