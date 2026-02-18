# backend/repositories/mysql/planned_transaction_repository.py
"""MySQL implementation of planned transaction repository."""

import logging
from typing import List, Dict, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.models.mysql.planned_transactions import PlannedTransactions as PTModel
from backend.repositories.base import IPlannedTransactionRepository

logger = logging.getLogger(__name__)


class MySQLPlannedTransactionRepository(IPlannedTransactionRepository):
    """MySQL implementation of planned transaction repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        try:
            pts = self.db.query(PTModel).offset(skip).limit(limit).all()
            return [self._serialize(pt) for pt in pts]
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af planlagte transaktioner: {e}")

    def get_by_id(self, pt_id: int) -> Optional[Dict]:
        try:
            pt = (
                self.db.query(PTModel)
                .filter(PTModel.idPlannedTransactions == pt_id)
                .first()
            )
            return self._serialize(pt) if pt else None
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af planlagt transaktion: {e}")

    def create(self, pt_data: Dict) -> Dict:
        try:
            db_pt = PTModel(**pt_data)
            self.db.add(db_pt)
            self.db.commit()
            self.db.refresh(db_pt)
            return self._serialize(db_pt)
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Fejl ved oprettelse af planlagt transaktion: {e}")

    def update(self, pt_id: int, pt_data: Dict) -> Optional[Dict]:
        try:
            db_pt = (
                self.db.query(PTModel)
                .filter(PTModel.idPlannedTransactions == pt_id)
                .first()
            )
            if not db_pt:
                return None

            for key, value in pt_data.items():
                if hasattr(db_pt, key):
                    setattr(db_pt, key, value)

            self.db.commit()
            self.db.refresh(db_pt)
            return self._serialize(db_pt)
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Fejl ved opdatering af planlagt transaktion: {e}")

    @staticmethod
    def _serialize(pt: PTModel) -> Dict:
        """Convert SQLAlchemy model to dict."""
        return {
            "idPlannedTransactions": pt.idPlannedTransactions,
            "Transaction_idTransaction": pt.Transaction_idTransaction,
            "name": pt.name,
            "amount": float(pt.amount) if isinstance(pt.amount, Decimal) else pt.amount,
        }
