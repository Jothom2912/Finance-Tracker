from typing import List, Dict, Optional
from backend.repository import get_goal_repository, get_account_repository
from backend.shared.schemas.goal import GoalCreate, GoalBase

def get_goal_by_id(goal_id: int) -> Optional[Dict]:
    repo = get_goal_repository()
    return repo.get_by_id(goal_id)

def get_goals_by_account(account_id: int) -> List[Dict]:
    repo = get_goal_repository()
    return repo.get_all(account_id=account_id)

def create_goal(goal: GoalCreate) -> Dict:
    account_repo = get_account_repository()
    account = account_repo.get_by_id(goal.Account_idAccount)
    if not account:
        raise ValueError("Konto med dette ID findes ikke.")
    
    repo = get_goal_repository()
    goal_data = {
        "name": goal.name,
        "target_amount": goal.target_amount,
        "current_amount": goal.current_amount or 0.0,
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "status": goal.status or "active",
        "Account_idAccount": goal.Account_idAccount
    }
    return repo.create(goal_data)

def update_goal(goal_id: int, goal_data: GoalBase) -> Optional[Dict]:
    repo = get_goal_repository()
    existing = repo.get_by_id(goal_id)
    if not existing:
        return None
    
    update_data = {
        "name": goal_data.name,
        "target_amount": goal_data.target_amount,
        "current_amount": goal_data.current_amount,
        "target_date": goal_data.target_date.isoformat() if goal_data.target_date else None,
        "status": goal_data.status
    }
    return repo.update(goal_id, update_data)

def delete_goal(goal_id: int) -> bool:
    repo = get_goal_repository()
    return repo.delete(goal_id)
