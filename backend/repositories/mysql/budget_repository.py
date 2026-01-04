# backend/repositories/mysql/budget_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.models.mysql.budget import Budget as BudgetModel
from backend.repositories.base import IBudgetRepository

class MySQLBudgetRepository(IBudgetRepository):
    """MySQL implementation of budget repository."""
    
    def __init__(self, db: Session):
        """Initialize repository with database session.
        
        Args:
            db: Database session (required - must be provided via Depends(get_db))
        """
        if db is None:
            raise ValueError("db: Session parameter is required")
        self.db = db
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        try:
            from sqlalchemy.orm import joinedload
            query = self.db.query(BudgetModel)
            # ✅ FIX: Load categories relationship så vi kan få category_id
            query = query.options(joinedload(BudgetModel.categories))
            if account_id:
                query = query.filter(BudgetModel.Account_idAccount == account_id)
            budgets = query.all()
            self.db.commit()  # ✅ Commit efter read
            return [self._serialize_budget(b) for b in budgets]
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af budgetter: {e}")
    
    def get_by_id(self, budget_id: int) -> Optional[Dict]:
        try:
            from sqlalchemy.orm import joinedload
            budget = self.db.query(BudgetModel).options(
                joinedload(BudgetModel.categories)
            ).filter(
                BudgetModel.idBudget == budget_id
            ).first()
            self.db.commit()  # ✅ Commit efter read
            return self._serialize_budget(budget) if budget else None
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved hentning af budget: {e}")
    
    def create(self, budget_data: Dict) -> Dict:
        try:
            from backend.models.mysql.common import budget_category_association
            
            # ✅ FIX: Hent Category_idCategory hvis den er i budget_data
            category_id = budget_data.get("Category_idCategory") or budget_data.get("category_id")
            
            budget = BudgetModel(
                amount=budget_data.get("amount"),
                budget_date=budget_data.get("budget_date"),
                Account_idAccount=budget_data.get("Account_idAccount")
            )
            self.db.add(budget)
            self.db.flush()  # Flush for at få idBudget
            
            # ✅ FIX: Opret association hvis category_id er sat
            if category_id:
                self.db.execute(
                    budget_category_association.insert().values(
                        Budget_idBudget=budget.idBudget,
                        Category_idCategory=category_id
                    )
                )
            
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(budget)
            
            # ✅ FIX: Load categories relationship så _serialize_budget kan få category_id
            from sqlalchemy.orm import joinedload
            budget = self.db.query(BudgetModel).options(
                joinedload(BudgetModel.categories)
            ).filter(BudgetModel.idBudget == budget.idBudget).first()
            
            return self._serialize_budget(budget)
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved oprettelse af budget: {e}")
    
    def update(self, budget_id: int, budget_data: Dict) -> Dict:
        try:
            from backend.models.mysql.common import budget_category_association
            from sqlalchemy.orm import joinedload
            
            budget = self.db.query(BudgetModel).options(
                joinedload(BudgetModel.categories)
            ).filter(
                BudgetModel.idBudget == budget_id
            ).first()
            if not budget:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                raise ValueError(f"Budget {budget_id} not found")
            
            if "amount" in budget_data:
                budget.amount = budget_data["amount"]
            if "budget_date" in budget_data:
                budget.budget_date = budget_data["budget_date"]
            
            # ✅ FIX: Håndter Category_idCategory update
            category_id = budget_data.get("Category_idCategory") or budget_data.get("category_id")
            if category_id is not None:
                # Slet eksisterende associations
                self.db.execute(
                    budget_category_association.delete().where(
                        budget_category_association.c.Budget_idBudget == budget_id
                    )
                )
                # Opret ny association
                self.db.execute(
                    budget_category_association.insert().values(
                        Budget_idBudget=budget_id,
                        Category_idCategory=category_id
                    )
                )
            
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(budget)
            
            # ✅ FIX: Reload med categories relationship
            budget = self.db.query(BudgetModel).options(
                joinedload(BudgetModel.categories)
            ).filter(BudgetModel.idBudget == budget_id).first()
            
            return self._serialize_budget(budget)
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved opdatering af budget: {e}")
    
    def delete(self, budget_id: int) -> bool:
        try:
            budget = self.db.query(BudgetModel).filter(
                BudgetModel.idBudget == budget_id
            ).first()
            if not budget:
                self.db.rollback()  # ✅ Rollback når objekt ikke findes
                return False
            
            self.db.delete(budget)
            self.db.commit()  # ✅ Commit efter write
            return True
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved sletning af budget: {e}")
    
    @staticmethod
    def _serialize_budget(budget: BudgetModel) -> Dict:
        """Serialiser budget til dict - SKAL inkludere Category_idCategory"""
        # ✅ FIX: Hent category_id fra categories relationship
        # Budget har many-to-many med Category, så vi tager første category
        category_id = None
        if hasattr(budget, 'categories') and budget.categories:
            if len(budget.categories) > 0:
                category_id = budget.categories[0].idCategory
        else:
            # Hvis categories ikke er loaded, prøv at hente direkte fra association
            # Dette kan ske hvis relationship ikke er eager loaded
            print(f"⚠️ WARNING: Budget {budget.idBudget} har ikke categories relationship loaded")
        
        return {
            "idBudget": budget.idBudget,
            "amount": float(budget.amount) if budget.amount else 0.0,
            "budget_date": budget.budget_date.isoformat() if budget.budget_date else None,
            "Account_idAccount": budget.Account_idAccount,
            "Category_idCategory": category_id  # ✅ KRITISK - må ikke mangle!
        }

