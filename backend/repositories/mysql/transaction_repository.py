# backend/repositories/mysql/transaction_repository.py
from typing import List, Dict, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from backend.database.mysql import SessionLocal
from backend.models.mysql.transaction import Transaction as TransactionModel
from backend.models.mysql.category import Category as CategoryModel
from backend.repositories.base import ITransactionRepository

class MySQLTransactionRepository(ITransactionRepository):
    """MySQL implementation of transaction repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        type: Optional[str] = None,
        month: Optional[str] = None,
        year: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        query = self.db.query(TransactionModel)
        
        if start_date:
            query = query.filter(TransactionModel.date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.date <= end_date)
        if category_id:
            query = query.filter(TransactionModel.Category_idCategory == category_id)
        if account_id:
            query = query.filter(TransactionModel.Account_idAccount == account_id)
        if type:
            query = query.filter(TransactionModel.type == type)
        if month:
            query = query.filter(extract('month', TransactionModel.date) == int(month))
        if year:
            query = query.filter(extract('year', TransactionModel.date) == int(year))
        
        transactions = query.order_by(TransactionModel.date.desc()).offset(offset).limit(limit).all()
        return [self._serialize_transaction(t) for t in transactions]
    
    def get_by_id(self, transaction_id: int) -> Optional[Dict]:
        transaction = self.db.query(TransactionModel).filter(
            TransactionModel.idTransaction == transaction_id
        ).first()
        return self._serialize_transaction(transaction) if transaction else None
    
    def create(self, transaction_data: Dict) -> Dict:
        transaction = TransactionModel(**transaction_data)
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return self._serialize_transaction(transaction)
    
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        transaction = self.db.query(TransactionModel).filter(
            TransactionModel.idTransaction == transaction_id
        ).first()
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        for key, value in transaction_data.items():
            setattr(transaction, key, value)
        
        self.db.commit()
        self.db.refresh(transaction)
        return self._serialize_transaction(transaction)
    
    def delete(self, transaction_id: int) -> bool:
        transaction = self.db.query(TransactionModel).filter(
            TransactionModel.idTransaction == transaction_id
        ).first()
        if not transaction:
            return False
        self.db.delete(transaction)
        self.db.commit()
        return True
    
    def search(
        self,
        search_text: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None
    ) -> List[Dict]:
        query = self.db.query(TransactionModel)
        
        if search_text:
            search_pattern = f"%{search_text}%"
            query = query.filter(TransactionModel.description.ilike(search_pattern))
        
        if start_date:
            query = query.filter(TransactionModel.date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.date <= end_date)
        if category_id:
            query = query.filter(TransactionModel.Category_idCategory == category_id)
        
        transactions = query.order_by(TransactionModel.date.desc()).all()
        return [self._serialize_transaction(t) for t in transactions]
    
    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        query = self.db.query(TransactionModel)
        
        if start_date:
            query = query.filter(TransactionModel.date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.date <= end_date)
        
        transactions = query.all()
        
        summary = {}
        for t in transactions:
            category = self.db.query(CategoryModel).filter(
                CategoryModel.idCategory == t.Category_idCategory
            ).first()
            cat_name = category.name if category else "Unknown"
            
            if cat_name not in summary:
                summary[cat_name] = {"count": 0, "total": 0.0}
            
            summary[cat_name]["count"] += 1
            summary[cat_name]["total"] += float(t.amount) if t.amount else 0.0
        
        return summary
    
    def get_expenses_by_category_for_period(
        self,
        month: int,
        year: int,
        account_id: int
    ) -> Dict[int, float]:
        """Get aggregated expenses by category for a specific month/year and account."""
        expenses_by_category = self.db.query(
            TransactionModel.Category_idCategory.label('category_id'),
            func.sum(TransactionModel.amount).label('total_spent')
        ).filter(
            TransactionModel.Account_idAccount == account_id,
            extract('month', TransactionModel.date) == month,
            extract('year', TransactionModel.date) == year,
            TransactionModel.amount < 0  # Expenses are negative
        ).group_by(
            TransactionModel.Category_idCategory
        ).all()

        # Return as {category_id: total_spent} (positive number for expense)
        return {row.category_id: abs(float(row.total_spent)) for row in expenses_by_category if row.category_id is not None}
        return {
            "idTransaction": transaction.idTransaction,
            "amount": float(transaction.amount) if transaction.amount else 0.0,
            "description": transaction.description,
            "date": transaction.date.isoformat() if transaction.date else None,
            "type": transaction.type,
            "Category_idCategory": transaction.Category_idCategory,
            "Account_idAccount": transaction.Account_idAccount
        }

