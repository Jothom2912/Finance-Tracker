from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy.exc import IntegrityError

from backend.models.mysql.goal import Goal as GoalModel
from backend.models.mysql.account import Account as AccountModel
from backend.shared.schemas.goal import GoalCreate, GoalBase

# --- CRUD Funktioner ---

def get_goal_by_id(db: Session, goal_id: int) -> Optional[GoalModel]:
    """Henter et mål baseret på ID."""
    return db.query(GoalModel).filter(GoalModel.idGoal == goal_id).first()

def get_goals_by_account(db: Session, account_id: int) -> List[GoalModel]:
    """Henter alle mål tilknyttet en specifik konto."""
    return db.query(GoalModel).filter(GoalModel.Account_idAccount == account_id).all()

def create_goal(db: Session, goal: GoalCreate) -> GoalModel:
    """Opretter et nyt mål tilknyttet en konto."""
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
        db.add(db_goal)
        db.commit()
        db.refresh(db_goal)
        return db_goal
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved oprettelse af mål.")

def update_goal(db: Session, goal_id: int, goal_data: GoalBase) -> Optional[GoalModel]:
    """Opdaterer et mål."""
    db_goal = get_goal_by_id(db, goal_id)
    if not db_goal:
        return None

    update_data = goal_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_goal, key, value)
    
    try:
        db.commit()
        db.refresh(db_goal)
        return db_goal
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl ved opdatering af mål.")