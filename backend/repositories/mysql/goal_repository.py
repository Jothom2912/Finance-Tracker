# backend/repositories/mysql/goal_repository.py
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.models.mysql.goal import Goal as GoalModel
from backend.repositories.base import IGoalRepository

class MySQLGoalRepository(IGoalRepository):
    """MySQL implementation of goal repository."""
    
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
            query = self.db.query(GoalModel)
            if account_id:
                query = query.filter(GoalModel.Account_idAccount == account_id)
            goals = query.all()
            return [self._serialize_goal(g) for g in goals]
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af mål: {e}")
    
    def get_by_id(self, goal_id: int) -> Optional[Dict]:
        try:
            goal = self.db.query(GoalModel).filter(GoalModel.idGoal == goal_id).first()
            return self._serialize_goal(goal) if goal else None
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af mål: {e}")
    
    def create(self, goal_data: Dict) -> Dict:
        try:
            goal = GoalModel(**goal_data)
            self.db.add(goal)
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(goal)
            return self._serialize_goal(goal)
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved oprettelse af mål: {e}")
    
    def update(self, goal_id: int, goal_data: Dict) -> Dict:
        try:
            goal = self.db.query(GoalModel).filter(GoalModel.idGoal == goal_id).first()
            if not goal:
                raise ValueError(f"Goal {goal_id} not found")
            for key, value in goal_data.items():
                setattr(goal, key, value)
            self.db.commit()  # ✅ Commit efter write
            self.db.refresh(goal)
            return self._serialize_goal(goal)
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved opdatering af mål: {e}")
    
    def delete(self, goal_id: int) -> bool:
        try:
            goal = self.db.query(GoalModel).filter(GoalModel.idGoal == goal_id).first()
            if not goal:
                return False
            self.db.delete(goal)
            self.db.commit()  # ✅ Commit efter write
            return True
        except Exception as e:
            self.db.rollback()  # ✅ Rollback på fejl
            raise ValueError(f"Fejl ved sletning af mål: {e}")
    
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

