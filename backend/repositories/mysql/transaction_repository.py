# backend/repositories/mysql/transaction_repository.py
from typing import List, Dict, Optional
from datetime import date
from sqlalchemy.orm import Session
from backend.models.mysql.transaction import Transaction as TransactionModel
from backend.models.mysql.category import Category as CategoryModel
from backend.repositories.base import ITransactionRepository

class MySQLTransactionRepository(ITransactionRepository):
    """MySQL implementation of transaction repository."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session.
        
        Args:
            db: Database session (required - must be provided via Depends(get_db))
        """
        if db is None:
            raise ValueError("db: Session parameter is required")
        self.db = db
    
    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        try:
            query = self.db.query(TransactionModel)
            
            if start_date:
                query = query.filter(TransactionModel.date >= start_date)
            if end_date:
                query = query.filter(TransactionModel.date <= end_date)
            if category_id:
                query = query.filter(TransactionModel.Category_idCategory == category_id)
            if account_id:
                query = query.filter(TransactionModel.Account_idAccount == account_id)
            
            transactions = query.order_by(TransactionModel.date.desc()).offset(offset).limit(limit).all()
            self.db.commit()  # ✅ Commit efter read
            return [self._serialize_transaction(t) for t in transactions]
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af transaktioner: {e}")
    
    def get_by_id(self, transaction_id: int) -> Optional[Dict]:
        try:
            transaction = self.db.query(TransactionModel).filter(
                TransactionModel.idTransaction == transaction_id
            ).first()
            self.db.commit()  # ✅ Commit efter read
            return self._serialize_transaction(transaction) if transaction else None
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af transaktion: {e}")
    
    def create(self, transaction_data: Dict) -> Dict:
        """Create transaction - håndter date korrekt."""
        try:
            # Håndter date - konverter til datetime hvis det er date objekt eller string
            if "date" in transaction_data:
                date_value = transaction_data["date"]
                if isinstance(date_value, date):
                    from datetime import datetime
                    transaction_data["date"] = datetime.combine(date_value, datetime.min.time())
                elif isinstance(date_value, str):
                    from datetime import datetime
                    try:
                        # Prøv at parse ISO format eller standard format
                        parsed_date = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                        transaction_data["date"] = datetime.combine(parsed_date.date(), datetime.min.time())
                    except:
                        try:
                            parsed_date = datetime.strptime(date_value, '%Y-%m-%d')
                            transaction_data["date"] = datetime.combine(parsed_date.date(), datetime.min.time())
                        except:
                            raise ValueError(f"Invalid date format: {date_value}")
            elif "date" not in transaction_data:
                # Hvis date mangler, sæt default til i dag
                from datetime import datetime
                transaction_data["date"] = datetime.now()
            
            transaction = TransactionModel(**transaction_data)
            self.db.add(transaction)
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(transaction)
            return self._serialize_transaction(transaction)
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved oprettelse af transaktion: {e}")
    
    def update(self, transaction_id: int, transaction_data: Dict) -> Dict:
        try:
            transaction = self.db.query(TransactionModel).filter(
                TransactionModel.idTransaction == transaction_id
            ).first()
            if not transaction:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                raise ValueError(f"Transaction {transaction_id} not found")
            
            for key, value in transaction_data.items():
                setattr(transaction, key, value)
            
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(transaction)
            return self._serialize_transaction(transaction)
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved opdatering af transaktion: {e}")
    
    def delete(self, transaction_id: int) -> bool:
        try:
            transaction = self.db.query(TransactionModel).filter(
                TransactionModel.idTransaction == transaction_id
            ).first()
            if not transaction:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                return False
            
            self.db.delete(transaction)
            self.db.commit()  # ✅ Commit efter write
            return True
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved sletning af transaktion: {e}")
    
    def search(
        self,
        search_text: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None
    ) -> List[Dict]:
        try:
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
            self.db.commit()  # ✅ Commit efter read
            return [self._serialize_transaction(t) for t in transactions]
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved søgning af transaktioner: {e}")
    
    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        try:
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
            
            self.db.commit()  # ✅ Commit efter read
            return summary
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af kategori summary: {e}")
    
    @staticmethod
    def _serialize_transaction(transaction: TransactionModel) -> Dict:
        """BRUG 'date' IKKE 'transaction_date' - konverter datetime til date objekt."""
        date_value = None
        if transaction.date:
            try:
                # If it's a datetime, extract just the date part
                if hasattr(transaction.date, 'date'):
                    date_value = transaction.date.date()
                elif hasattr(transaction.date, 'isoformat'):
                    # It's already a date object
                    date_value = transaction.date
                elif isinstance(transaction.date, str):
                    from datetime import datetime
                    try:
                        date_value = datetime.fromisoformat(transaction.date.replace('Z', '+00:00')).date()
                    except:
                        try:
                            date_value = datetime.strptime(transaction.date, "%Y-%m-%d").date()
                        except:
                            date_value = None
                else:
                    date_value = transaction.date
            except Exception as e:
                print(f"WARNING: Error converting date for transaction {transaction.idTransaction}: {e}")
                date_value = None
        
        return {
            "idTransaction": transaction.idTransaction,
            "amount": float(transaction.amount) if transaction.amount else 0.0,
            "description": transaction.description,
            "date": date_value,  # ✅ BRUG "date" konsistent
            "type": transaction.type,
            "Category_idCategory": transaction.Category_idCategory,
            "Account_idAccount": transaction.Account_idAccount,
            "created_at": transaction.created_at.isoformat() if hasattr(transaction, 'created_at') and transaction.created_at else None
        }

