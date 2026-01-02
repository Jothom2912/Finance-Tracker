from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.database.mysql import SessionLocal
from backend.models.mysql.planned_transactions import PlannedTransactions as PlannedTransactionModel
from backend.repositories.base import IPlannedTransaction

class MySQLPlannedTransactionRepository(IPlannedTransaction):
    """MySQL implementation of planned transaction repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        query = self.db.query(PlannedTransactionModel)
        # PlannedTransactions doesn't have account_id filter
        planned_transactions = query.all()
        return [self._serialize_planned_transaction(pt) for pt in planned_transactions]
    
    def get_by_id(self, planned_transaction_id: int) -> Optional[Dict]:
        planned_transaction = self.db.query(PlannedTransactionModel).filter(PlannedTransactionModel.idPlannedTransactions == planned_transaction_id).first()
        return self._serialize_planned_transaction(planned_transaction) if planned_transaction else None
    
    def create(self, planned_transaction_data: Dict) -> Dict:
        planned_transaction = PlannedTransactionModel(
            name=planned_transaction_data.get("name"),
            amount=planned_transaction_data.get("amount"),
            Transaction_idTransaction=planned_transaction_data.get("Transaction_idTransaction")
        )
        self.db.add(planned_transaction)
        self.db.commit()
        self.db.refresh(planned_transaction)
        return self._serialize_planned_transaction(planned_transaction)
    
    def update(self, planned_transaction_id: int, planned_transaction_data: Dict) -> Dict:
        planned_transaction = self.db.query(PlannedTransactionModel).filter(PlannedTransactionModel.idPlannedTransactions == planned_transaction_id).first()
        if not planned_transaction:
            raise ValueError(f"Planned transaction {planned_transaction_id} not found")
        
        if "name" in planned_transaction_data:
            planned_transaction.name = planned_transaction_data["name"]
        if "amount" in planned_transaction_data:
            planned_transaction.amount = planned_transaction_data["amount"]
        if "Transaction_idTransaction" in planned_transaction_data:
            planned_transaction.Transaction_idTransaction = planned_transaction_data["Transaction_idTransaction"]
        
        self.db.commit()
        self.db.refresh(planned_transaction)
        return self._serialize_planned_transaction(planned_transaction)
    
    def delete(self, planned_transaction_id: int) -> bool:
        planned_transaction = self.db.query(PlannedTransactionModel).filter(PlannedTransactionModel.idPlannedTransactions == planned_transaction_id).first()
        if not planned_transaction:
            return False
        self.db.delete(planned_transaction)
        self.db.commit()
        return True
    
    @staticmethod
    def _serialize_planned_transaction(planned_transaction: PlannedTransactionModel) -> Dict:
        return {
            "idPlannedTransactions": planned_transaction.idPlannedTransactions,
            "name": planned_transaction.name,
            "amount": float(planned_transaction.amount) if planned_transaction.amount else None,
            "Transaction_idTransaction": planned_transaction.Transaction_idTransaction
        }