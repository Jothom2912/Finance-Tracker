"""
MySQL adapter for Budget repository.
"""
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from backend.budget.application.ports.outbound import IBudgetRepository
from backend.budget.domain.entities import Budget
from backend.models.mysql.budget import Budget as BudgetModel
from backend.models.mysql.common import budget_category_association


class MySQLBudgetRepository(IBudgetRepository):
    """MySQL implementation of budget repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, budget_id: int) -> Optional[Budget]:
        model = (
            self._db.query(BudgetModel)
            .options(joinedload(BudgetModel.categories))
            .filter(BudgetModel.idBudget == budget_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self, account_id: int) -> list[Budget]:
        models = (
            self._db.query(BudgetModel)
            .options(joinedload(BudgetModel.categories))
            .filter(BudgetModel.Account_idAccount == account_id)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def create(self, budget: Budget) -> Budget:
        model = BudgetModel(
            amount=budget.amount,
            budget_date=budget.budget_date,
            Account_idAccount=budget.account_id,
        )
        self._db.add(model)
        self._db.flush()

        if budget.category_id:
            self._db.execute(
                budget_category_association.insert().values(
                    Budget_idBudget=model.idBudget,
                    Category_idCategory=budget.category_id,
                )
            )

        self._db.commit()
        self._db.refresh(model)

        # Reload with categories relationship
        model = (
            self._db.query(BudgetModel)
            .options(joinedload(BudgetModel.categories))
            .filter(BudgetModel.idBudget == model.idBudget)
            .first()
        )

        return self._to_entity(model)

    def update(self, budget: Budget) -> Budget:
        model = (
            self._db.query(BudgetModel)
            .options(joinedload(BudgetModel.categories))
            .filter(BudgetModel.idBudget == budget.id)
            .first()
        )

        model.amount = budget.amount
        if budget.budget_date:
            model.budget_date = budget.budget_date
        if budget.account_id:
            model.Account_idAccount = budget.account_id

        # Update category via association table
        if budget.category_id is not None:
            self._db.execute(
                budget_category_association.delete().where(
                    budget_category_association.c.Budget_idBudget == budget.id
                )
            )
            self._db.execute(
                budget_category_association.insert().values(
                    Budget_idBudget=budget.id,
                    Category_idCategory=budget.category_id,
                )
            )

        self._db.commit()
        self._db.refresh(model)

        model = (
            self._db.query(BudgetModel)
            .options(joinedload(BudgetModel.categories))
            .filter(BudgetModel.idBudget == budget.id)
            .first()
        )

        return self._to_entity(model)

    def delete(self, budget_id: int) -> bool:
        model = (
            self._db.query(BudgetModel)
            .filter(BudgetModel.idBudget == budget_id)
            .first()
        )
        if not model:
            return False

        self._db.delete(model)
        self._db.commit()
        return True

    @staticmethod
    def _to_entity(model: BudgetModel) -> Budget:
        category_id = 0
        if hasattr(model, "categories") and model.categories:
            category_id = model.categories[0].idCategory

        return Budget(
            id=model.idBudget,
            amount=float(model.amount) if model.amount else 0.0,
            budget_date=model.budget_date,
            account_id=model.Account_idAccount,
            category_id=category_id,
        )
