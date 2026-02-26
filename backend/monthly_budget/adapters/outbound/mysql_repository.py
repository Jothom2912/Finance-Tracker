"""
MySQL adapter for MonthlyBudget repository.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from backend.monthly_budget.application.ports.outbound import IMonthlyBudgetRepository
from backend.monthly_budget.domain.entities import BudgetLine, MonthlyBudget
from backend.models.mysql.monthly_budget import (
    BudgetLine as BudgetLineModel,
    MonthlyBudget as MonthlyBudgetModel,
)


class MySQLMonthlyBudgetRepository(IMonthlyBudgetRepository):
    """MySQL implementation of monthly budget repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def get_by_id(self, budget_id: int) -> Optional[MonthlyBudget]:
        model = (
            self._db.query(MonthlyBudgetModel)
            .options(joinedload(MonthlyBudgetModel.lines))
            .filter(MonthlyBudgetModel.id == budget_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_by_account_and_period(
        self, account_id: int, month: int, year: int
    ) -> Optional[MonthlyBudget]:
        model = (
            self._db.query(MonthlyBudgetModel)
            .options(joinedload(MonthlyBudgetModel.lines))
            .filter(
                MonthlyBudgetModel.account_id == account_id,
                MonthlyBudgetModel.month == month,
                MonthlyBudgetModel.year == year,
            )
            .first()
        )
        return self._to_entity(model) if model else None

    def create(self, budget: MonthlyBudget) -> MonthlyBudget:
        model = MonthlyBudgetModel(
            month=budget.month,
            year=budget.year,
            account_id=budget.account_id,
        )
        for line in budget.lines:
            model.lines.append(
                BudgetLineModel(
                    category_id=line.category_id,
                    amount=line.amount,
                )
            )

        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)

        return self._to_entity(model)

    def update(self, budget: MonthlyBudget) -> MonthlyBudget:
        model = (
            self._db.query(MonthlyBudgetModel)
            .options(joinedload(MonthlyBudgetModel.lines))
            .filter(MonthlyBudgetModel.id == budget.id)
            .first()
        )
        if not model:
            raise ValueError(f"MonthlyBudget {budget.id} not found")

        model.lines.clear()
        self._db.flush()

        for line in budget.lines:
            model.lines.append(
                BudgetLineModel(
                    category_id=line.category_id,
                    amount=line.amount,
                )
            )

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def delete(self, budget_id: int) -> bool:
        model = (
            self._db.query(MonthlyBudgetModel)
            .filter(MonthlyBudgetModel.id == budget_id)
            .first()
        )
        if not model:
            return False
        self._db.delete(model)
        self._db.commit()
        return True

    @staticmethod
    def _to_entity(model: MonthlyBudgetModel) -> MonthlyBudget:
        return MonthlyBudget(
            id=model.id,
            month=model.month,
            year=model.year,
            account_id=model.account_id,
            created_at=model.created_at,
            lines=[
                BudgetLine(
                    id=line.id,
                    category_id=line.category_id,
                    amount=float(line.amount) if line.amount else 0.0,
                )
                for line in (model.lines or [])
            ],
        )
