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
        from sqlalchemy.orm import joinedload
        budget = BudgetModel(
            amount=budget_data.get("amount"),
            budget_date=budget_data.get("budget_date"),
            Account_idAccount=budget_data.get("Account_idAccount")
        )
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        
        # Handle category association if category_id is provided
        category_id = budget_data.get("category_id")
        if category_id:
            from backend.models.mysql.common import budget_category_association
            stmt = budget_category_association.insert().values(
                Budget_idBudget=budget.idBudget,
                Category_idCategory=category_id
            )
            self.db.execute(stmt)
            self.db.commit()
            
            # Reload with categories
            budget = self.db.query(BudgetModel).options(
                joinedload(BudgetModel.categories)
            ).filter(BudgetModel.idBudget == budget.idBudget).first()
        
        return self._serialize_budget(budget)
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        from sqlalchemy.orm import joinedload
        budget = self.db.query(BudgetModel).filter(
            BudgetModel.idBudget == budget_id
        ).first()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        
        if "amount" in budget_data:
            budget.amount = budget_data["amount"]
        if "budget_date" in budget_data:
            budget.budget_date = budget_data["budget_date"]
        
        # Handle category association update if category_id is provided
        category_id = budget_data.get("category_id")
        if category_id is not None:
            from backend.models.mysql.common import budget_category_association
            
            # Remove existing categories
            delete_stmt = budget_category_association.delete().where(
                budget_category_association.c.Budget_idBudget == budget_id
            )
            self.db.execute(delete_stmt)
            
            # Add new category
            insert_stmt = budget_category_association.insert().values(
                Budget_idBudget=budget_id,
                Category_idCategory=category_id
            )
            self.db.execute(insert_stmt)
            
            # Reload with categories
            budget = self.db.query(BudgetModel).options(
                joinedload(BudgetModel.categories)
            ).filter(BudgetModel.idBudget == budget_id).first()
        
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
        from sqlalchemy.orm import joinedload
        # Ensure categories are loaded
        if not hasattr(budget, 'categories') or budget.categories is None:
            # If not loaded, we need to load them, but since we're in serialize, assume they are loaded
            pass
        return {
            "idBudget": budget.idBudget,
            "amount": float(budget.amount) if budget.amount else 0.0,
            "budget_date": budget.budget_date.isoformat() if budget.budget_date else None,
            "Account_idAccount": budget.Account_idAccount,
            "categories": [{"idCategory": c.idCategory, "name": c.name} for c in budget.categories] if budget.categories else []
        }

