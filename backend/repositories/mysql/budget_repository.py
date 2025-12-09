# backend/repositories/mysql/budget_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.database.mysql import SessionLocal
from backend.models.mysql.budget import Budget as BudgetModel
from backend.repositories.base import IBudgetRepository

class MySQLBudgetRepository(IBudgetRepository):
    """MySQL implementation of budget repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        query = self.db.query(BudgetModel)
        if account_id:
            query = query.filter(BudgetModel.Account_idAccount == account_id)
        budgets = query.all()
        return [self._serialize_budget(b) for b in budgets]
    
    def get_by_id(self, budget_id: int) -> Optional[Dict]:
        budget = self.db.query(BudgetModel).filter(
            BudgetModel.idBudget == budget_id
        ).first()
        return self._serialize_budget(budget) if budget else None
    
    def create(self, budget_data: Dict) -> Dict:
        budget = BudgetModel(
            amount=budget_data.get("amount"),
            budget_date=budget_data.get("budget_date"),
            Account_idAccount=budget_data.get("Account_idAccount")
        )
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return self._serialize_budget(budget)
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        budget = self.db.query(BudgetModel).filter(
            BudgetModel.idBudget == budget_id
        ).first()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        
        if "amount" in budget_data:
            budget.amount = budget_data["amount"]
        if "budget_date" in budget_data:
            budget.budget_date = budget_data["budget_date"]
        
        self.db.commit()
        self.db.refresh(budget)
        return self._serialize_budget(budget)
    
    def delete(self, budget_id: int) -> bool:
        budget = self.db.query(BudgetModel).filter(
            BudgetModel.idBudget == budget_id
        ).first()
        if not budget:
            return False
        self.db.delete(budget)
        self.db.commit()
        return True
    
    @staticmethod
    def _serialize_budget(budget: BudgetModel) -> Dict:
        return {
            "idBudget": budget.idBudget,
            "amount": float(budget.amount) if budget.amount else 0.0,
            "budget_date": budget.budget_date.isoformat() if budget.budget_date else None,
            "Account_idAccount": budget.Account_idAccount
        }

