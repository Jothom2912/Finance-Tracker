"""
MySQL adapter for Transaction and PlannedTransaction repositories.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy.orm import Session

from backend.models.mysql.category import Category as CategoryModel
from backend.models.mysql.planned_transactions import (
    PlannedTransactions as PlannedTransactionModel,
)
from backend.models.mysql.transaction import Transaction as TransactionModel
from backend.transaction.application.ports.outbound import (
    IPlannedTransactionRepository,
    ITransactionRepository,
)
from backend.transaction.domain.entities import PlannedTransaction, Transaction

logger = logging.getLogger(__name__)


class MySQLTransactionRepository(ITransactionRepository):
    """MySQL implementation of transaction repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        model = (
            self._db.query(TransactionModel)
            .filter(TransactionModel.idTransaction == transaction_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Transaction]:
        query = self._db.query(TransactionModel)

        if start_date:
            query = query.filter(TransactionModel.date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.date <= end_date)
        if category_id:
            query = query.filter(
                TransactionModel.Category_idCategory == category_id
            )
        if account_id:
            query = query.filter(
                TransactionModel.Account_idAccount == account_id
            )

        models = (
            query.order_by(TransactionModel.date.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def create(self, transaction: Transaction) -> Transaction:
        date_value = transaction.date
        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            date_value = datetime.combine(date_value, datetime.min.time())

        model = TransactionModel(
            amount=transaction.amount,
            description=transaction.description,
            date=date_value,
            type=transaction.type,
            Category_idCategory=transaction.category_id,
            Account_idAccount=transaction.account_id,
            created_at=transaction.created_at or datetime.now(),
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(self, transaction: Transaction) -> Optional[Transaction]:
        model = (
            self._db.query(TransactionModel)
            .filter(TransactionModel.idTransaction == transaction.id)
            .first()
        )
        if not model:
            return None

        model.amount = transaction.amount
        model.description = transaction.description
        model.type = transaction.type
        model.Category_idCategory = transaction.category_id
        model.Account_idAccount = transaction.account_id

        if transaction.date:
            date_value = transaction.date
            if isinstance(date_value, date) and not isinstance(date_value, datetime):
                date_value = datetime.combine(date_value, datetime.min.time())
            model.date = date_value

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def delete(self, transaction_id: int) -> bool:
        model = (
            self._db.query(TransactionModel)
            .filter(TransactionModel.idTransaction == transaction_id)
            .first()
        )
        if not model:
            return False

        self._db.delete(model)
        self._db.commit()
        return True

    def search(
        self,
        search_text: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
    ) -> list[Transaction]:
        query = self._db.query(TransactionModel)

        if search_text:
            query = query.filter(
                TransactionModel.description.ilike(f"%{search_text}%")
            )
        if start_date:
            query = query.filter(TransactionModel.date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.date <= end_date)
        if category_id:
            query = query.filter(
                TransactionModel.Category_idCategory == category_id
            )

        models = query.order_by(TransactionModel.date.desc()).all()
        return [self._to_entity(m) for m in models]

    def get_summary_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict:
        query = self._db.query(TransactionModel)

        if start_date:
            query = query.filter(TransactionModel.date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.date <= end_date)

        transactions = query.all()

        summary: Dict = {}
        for t in transactions:
            category = (
                self._db.query(CategoryModel)
                .filter(CategoryModel.idCategory == t.Category_idCategory)
                .first()
            )
            cat_name = category.name if category else "Unknown"

            if cat_name not in summary:
                summary[cat_name] = {"count": 0, "total": 0.0}

            summary[cat_name]["count"] += 1
            summary[cat_name]["total"] += float(t.amount) if t.amount else 0.0

        return summary

    @staticmethod
    def _to_entity(model: TransactionModel) -> Transaction:
        # Parse date - DB stores datetime, entity uses date
        date_value = None
        if model.date:
            if hasattr(model.date, "date"):
                date_value = model.date.date()
            elif isinstance(model.date, date):
                date_value = model.date
        if date_value is None:
            date_value = date.today()

        return Transaction(
            id=model.idTransaction,
            amount=float(model.amount) if model.amount else 0.0,
            description=model.description,
            date=date_value,
            type=model.type or "expense",
            category_id=model.Category_idCategory,
            account_id=model.Account_idAccount,
            created_at=(
                model.created_at
                if hasattr(model, "created_at")
                else None
            ),
        )


class MySQLPlannedTransactionRepository(IPlannedTransactionRepository):
    """MySQL implementation of planned transaction repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, pt_id: int) -> Optional[PlannedTransaction]:
        model = (
            self._db.query(PlannedTransactionModel)
            .filter(PlannedTransactionModel.idPlannedTransactions == pt_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[PlannedTransaction]:
        models = (
            self._db.query(PlannedTransactionModel)
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def create(self, planned: PlannedTransaction) -> PlannedTransaction:
        model = PlannedTransactionModel(
            name=planned.name,
            amount=planned.amount,
            Transaction_idTransaction=planned.transaction_id,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(self, planned: PlannedTransaction) -> Optional[PlannedTransaction]:
        model = (
            self._db.query(PlannedTransactionModel)
            .filter(PlannedTransactionModel.idPlannedTransactions == planned.id)
            .first()
        )
        if not model:
            return None

        if planned.name is not None:
            model.name = planned.name
        if planned.amount is not None:
            model.amount = planned.amount
        if planned.transaction_id is not None:
            model.Transaction_idTransaction = planned.transaction_id

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: PlannedTransactionModel) -> PlannedTransaction:
        return PlannedTransaction(
            id=model.idPlannedTransactions,
            name=model.name,
            amount=(
                float(model.amount)
                if isinstance(model.amount, Decimal)
                else (model.amount or 0.0)
            ),
            transaction_id=model.Transaction_idTransaction,
        )
