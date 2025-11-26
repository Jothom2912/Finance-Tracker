from sqlalchemy.orm import Session
from typing import Optional, List

from ..models.planned_transactions import PlannedTransactions as PTModel
from ..schemas.planned_transactions import PlannedTransactionsCreate, PlannedTransactionsBase

# --- CRUD Funktioner ---

def get_planned_transaction_by_id(db: Session, pt_id: int) -> Optional[PTModel]:
    """Henter en planlagt transaktion baseret på ID."""
    return db.query(PTModel).filter(PTModel.idPlannedTransactions == pt_id).first()

def get_planned_transactions(db: Session, skip: int = 0, limit: int = 100) -> List[PTModel]:
    """Henter en pagineret liste over planlagte transaktioner."""
    return db.query(PTModel).offset(skip).limit(limit).all()

def create_planned_transaction(db: Session, pt_data: PlannedTransactionsCreate) -> PTModel:
    """Opretter en ny planlagt transaktion."""
    
    # Bemærk: Din model har ikke direkte Account_id, men Transaction_idTransaction er valgfri.
    # Her antages det, at `pt_data` kun indeholder felterne fra PTBase.
    
    db_pt = PTModel(**pt_data.model_dump())
    
    try:
        db.add(db_pt)
        db.commit()
        db.refresh(db_pt)
        return db_pt
    except Exception as e:
        db.rollback()
        raise ValueError(f"Fejl ved oprettelse af planlagt transaktion: {e}")

def update_planned_transaction(db: Session, pt_id: int, pt_data: PlannedTransactionsBase) -> Optional[PTModel]:
    """Opdaterer en planlagt transaktion."""
    db_pt = get_planned_transaction_by_id(db, pt_id)
    if not db_pt:
        return None
        
    update_data = pt_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_pt, key, value)
    
    try:
        db.commit()
        db.refresh(db_pt)
        return db_pt
    except Exception as e:
        db.rollback()
        raise ValueError(f"Fejl ved opdatering af planlagt transaktion: {e}")