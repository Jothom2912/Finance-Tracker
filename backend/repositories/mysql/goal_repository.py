# backend/repositories/mysql/goal_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.database.mysql import SessionLocal
from backend.models.mysql.goal import Goal as GoalModel
from backend.repositories.base import IGoalRepository

class MySQLGoalRepository(IGoalRepository):
    """MySQL implementation of goal repository."""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        query = self.db.query(GoalModel)
        if account_id:
            query = query.filter(GoalModel.Account_idAccount == account_id)
        goals = query.all()
        return [self._serialize_goal(g) for g in goals]
    
    def get_by_id(self, goal_id: int) -> Optional[Dict]:
        goal = self.db.query(GoalModel).filter(GoalModel.idGoal == goal_id).first()
        return self._serialize_goal(goal) if goal else None
    
    def create(self, goal_data: Dict) -> Dict:
        goal = GoalModel(**goal_data)
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return self._serialize_goal(goal)
    
    def update(self, goal_id: int, goal_data: Dict) -> Dict:
        goal = self.db.query(GoalModel).filter(GoalModel.idGoal == goal_id).first()
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        for key, value in goal_data.items():
            setattr(goal, key, value)
        self.db.commit()
        self.db.refresh(goal)
        return self._serialize_goal(goal)
    
    def delete(self, goal_id: int) -> bool:
        goal = self.db.query(GoalModel).filter(GoalModel.idGoal == goal_id).first()
        if not goal:
            return False
        self.db.delete(goal)
        self.db.commit()
        return True
    
    @staticmethod
    def _serialize_goal(goal: GoalModel) -> Dict:
        return {
            "idGoal": goal.idGoal,
            "name": goal.name,
            "target_amount": float(goal.target_amount) if goal.target_amount else 0.0,
            "current_amount": float(goal.current_amount) if goal.current_amount else 0.0,
            "target_date": goal.target_date.isoformat() if goal.target_date else None,
            "status": goal.status,
            "Account_idAccount": goal.Account_idAccount
        }

