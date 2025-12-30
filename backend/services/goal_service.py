from backend.repositories import get_goal_repository
from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy.exc import IntegrityError

from backend.models.mysql.goal import Goal as GoalModel
from backend.models.mysql.account import Account as AccountModel
from backend.shared.schemas.goal import GoalCreate, GoalBase

# --- CRUD Funktioner ---

def get_goal_by_id( goal_id: int) -> Optional[GoalModel]:
    """Henter et mål baseret på ID."""
    repo= get_goal_repository()
    return repo.get_by_id(goal_id)

def get_goals_by_account( account_id: int) -> List[GoalModel]:
    """Henter alle mål tilknyttet en specifik konto."""
    repo= get_goal_repository()
    return repo.get_goals_by_account(account_id)

def create_goal(db: Session, goal: GoalCreate) -> GoalModel:
    """Opretter et nyt mål tilknyttet en konto."""
    repo= get_goal_repository()
    account = db.query(AccountModel).filter(AccountModel.idAccount == goal.Account_idAccount).first()
    if not account:
        raise ValueError("Konto med dette ID findes ikke.")
        
    db_goal = GoalModel(
        name=goal.name,
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        target_date=goal.target_date,
        status=goal.status,
        Account_idAccount=goal.Account_idAccount
    )
    
    try:
        repo.create(db_goal)
        return db_goal
    except IntegrityError:
        raise ValueError("Integritetsfejl ved oprettelse af mål.")

def update_goal(goal_id: int, goal_data: GoalBase) -> Optional[GoalModel]:
    """Opdaterer et mål."""
    repo = get_goal_repository()
    db_goal = repo.get_by_id(goal_id)
    if not db_goal:
        return None

    update_data = goal_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_goal, key, value)
    
    try:
        repo.update(db_goal)
        return db_goal
    except IntegrityError:
        raise ValueError("Integritetsfejl ved opdatering af mål.")

def delete_goal(goal_id: int) -> bool:
    """Sletter et mål."""
    repo = get_goal_repository()
    db_goal = repo.get_by_id(goal_id)
    if not db_goal:
        return False
    
    try:
        repo.delete(goal_id)
        return True
    except IntegrityError:
        raise ValueError("Integritetsfejl ved sletning af mål.")