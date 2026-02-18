"""
MySQL implementation of Goal repository port.
"""
from typing import Optional

from sqlalchemy.orm import Session

from backend.goal.application.ports.outbound import IGoalRepository
from backend.goal.domain.entities import Goal
from backend.models.mysql.goal import Goal as GoalModel


class MySQLGoalRepository(IGoalRepository):
    """MySQL implementation of goal repository."""

    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, goal_id: int) -> Optional[Goal]:
        model = (
            self._db.query(GoalModel)
            .filter(GoalModel.idGoal == goal_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_all(self, account_id: Optional[int] = None) -> list[Goal]:
        query = self._db.query(GoalModel)
        if account_id:
            query = query.filter(GoalModel.Account_idAccount == account_id)
        models = query.all()
        return [self._to_entity(m) for m in models]

    def create(self, goal: Goal) -> Goal:
        model = GoalModel(
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            status=goal.status,
            Account_idAccount=goal.account_id,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def update(self, goal: Goal) -> Goal:
        model = (
            self._db.query(GoalModel)
            .filter(GoalModel.idGoal == goal.id)
            .first()
        )

        model.name = goal.name
        model.target_amount = goal.target_amount
        model.current_amount = goal.current_amount
        model.target_date = goal.target_date
        model.status = goal.status

        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

    def delete(self, goal_id: int) -> bool:
        model = (
            self._db.query(GoalModel)
            .filter(GoalModel.idGoal == goal_id)
            .first()
        )
        if not model:
            return False

        self._db.delete(model)
        self._db.commit()
        return True

    def _to_entity(self, model: GoalModel) -> Goal:
        return Goal(
            id=model.idGoal,
            name=model.name,
            target_amount=(
                float(model.target_amount) if model.target_amount else 0.0
            ),
            current_amount=(
                float(model.current_amount) if model.current_amount else 0.0
            ),
            target_date=model.target_date,
            status=model.status,
            account_id=model.Account_idAccount,
        )
