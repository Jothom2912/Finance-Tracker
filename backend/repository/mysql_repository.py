# backend/repository/mysql_repository.py
from typing import List, Dict, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.repository.base_repository import ITransactionRepository, ICategoryRepository
from backend.database import Transaction, Category, SessionLocal

class MySQLTransactionRepository(ITransactionRepository):
    """MySQL implementation of transaction repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        query = self.db.query(Transaction)
        
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        if category_id:
            query = query.filter(Transaction.category_id == category_id)
        
        transactions = query.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()
        
        return [self._serialize_transaction(t) for t in transactions]
    
    def get_by_id(self, transaction_id: int) -> Optional[Dict]:
        transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
        return self._serialize_transaction(transaction) if transaction else None
    
    def create(self, transaction_data: Dict) -> Dict:
        transaction = Transaction(**transaction_data)
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return self._serialize_transaction(transaction)
    
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        for key, value in transaction_data.items():
            setattr(transaction, key, value)
        
        self.db.commit()
        self.db.refresh(transaction)
        return self._serialize_transaction(transaction)
    
    def delete(self, transaction_id: int) -> bool:
        transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
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
        query = self.db.query(Transaction)
        
        if search_text:
            search_pattern = f"%{search_text}%"
            query = query.filter(
                Transaction.description.ilike(search_pattern) |
                Transaction.name.ilike(search_pattern) |
                Transaction.sender.ilike(search_pattern) |
                Transaction.recipient.ilike(search_pattern)
            )
        
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        if category_id:
            query = query.filter(Transaction.category_id == category_id)
        
        transactions = query.order_by(Transaction.date.desc()).all()
        return [self._serialize_transaction(t) for t in transactions]
    
    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        query = self.db.query(Transaction)
        
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        
        transactions = query.all()
        
        summary = {}
        for t in transactions:
            category = self.db.query(Category).filter(Category.id == t.category_id).first()
            cat_name = category.name if category else "Unknown"
            
            if cat_name not in summary:
                summary[cat_name] = {"count": 0, "total": 0}
            
            summary[cat_name]["count"] += 1
            summary[cat_name]["total"] += t.amount
        
        return summary
    
    @staticmethod
    def _serialize_transaction(transaction: Transaction) -> Dict:
        return {
            "id": transaction.id,
            "description": transaction.description,
            "amount": transaction.amount,
            "date": transaction.date.isoformat() if transaction.date else None,
            "type": transaction.type.value if transaction.type else "expense",
            "category_id": transaction.category_id,
            "balance_after": transaction.balance_after,
            "currency": transaction.currency,
            "sender": transaction.sender,
            "recipient": transaction.recipient,
            "name": transaction.name
        }


class MySQLCategoryRepository(ICategoryRepository):
    """MySQL implementation of category repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(self) -> List[Dict]:
        categories = self.db.query(Category).all()
        return [self._serialize_category(c) for c in categories]
    
    def get_by_id(self, category_id: int) -> Optional[Dict]:
        category = self.db.query(Category).filter(Category.id == category_id).first()
        return self._serialize_category(category) if category else None
    
    def create(self, name: str) -> Dict:
        category = Category(name=name)
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return self._serialize_category(category)
    
    def delete(self, category_id: int) -> bool:
        category = self.db.query(Category).filter(Category.id == category_id).first()
        if not category:
            return False
        self.db.delete(category)
        self.db.commit()
        return True
    
    @staticmethod
    def _serialize_category(category: Category) -> Dict:
        return {
            "id": category.id,
            "name": category.name,
            "type": category.type.value if category.type else "expense"
        }
