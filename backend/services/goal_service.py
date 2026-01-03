from backend.repositories import get_goal_repository
from typing import Optional, List

from backend.shared.schemas.goal import GoalCreate, GoalBase

# --- CRUD Funktioner ---

def get_goal_by_id( goal_id: int) -> Optional[dict]:
    """Henter et mål baseret på ID."""
    repo= get_goal_repository()
    return repo.get_by_id(goal_id)

def get_goals_by_account( account_id: int) -> List[dict]:
    """Henter alle mål tilknyttet en specifik konto."""
    repo= get_goal_repository()
    return repo.get_all(account_id=account_id)

def create_goal( goal: GoalCreate) -> dict:
    """Opretter et nyt mål tilknyttet en konto."""
    repo= get_goal_repository()
        
    db_goal = dict(
        name=goal.name,
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        target_date=goal.target_date,
        status=goal.status,
        Account_idAccount=goal.Account_idAccount
    )
    repo.create(db_goal)
    return db_goal

def update_goal(goal_id: int, goal_data: GoalBase) -> Optional[dict]:
    """Opdaterer et mål."""
    repo = get_goal_repository()
    db_goal = repo.get_by_id(goal_id)
    if not db_goal:
        return None

    update_data = goal_data.model_dump(exclude_unset=True)
    db_goal.update(update_data)
    
    repo.update(goal_id, db_goal)
    return db_goal

def delete_goal(goal_id: int) -> bool:
    """Sletter et mål."""
    repo = get_goal_repository()
    db_goal = repo.get_by_id(goal_id)
    if not db_goal:
        return False
    repo.delete(goal_id)
    return True