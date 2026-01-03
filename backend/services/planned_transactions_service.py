from backend.repositories import get_planned_transaction_repository
from typing import Optional, List

from backend.repositories.base import IPlannedTransaction
from backend.shared.schemas.planned_transactions import PlannedTransactionsCreate, PlannedTransactionsBase


# --- CRUD Funktioner ---

def get_planned_transaction_by_id(pt_id: int) -> Optional[dict]:
    """Henter en planlagt transaktion baseret på ID."""
    repo = get_planned_transaction_repository()
    data = repo.get_by_id(pt_id)
    return data

def get_planned_transactions(account_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[dict]:
    """Henter en pagineret liste over planlagte transaktioner."""
    repo = get_planned_transaction_repository()
    all_pts = repo.get_all(account_id=account_id)
    return all_pts[skip:skip + limit]

def create_planned_transaction( pt_data: PlannedTransactionsCreate) -> dict:
    """Opretter en ny planlagt transaktion."""
    repo = get_planned_transaction_repository()
    data = pt_data.model_dump()
    result = repo.create(data)
    return result

def update_planned_transaction( pt_id: int, pt_data: PlannedTransactionsBase) -> Optional[dict]:
    """Opdaterer en planlagt transaktion."""
    repo = get_planned_transaction_repository()
    data = pt_data.model_dump(exclude_unset=True)
    result = repo.update(pt_id, data)
    return result if result else None

def delete_planned_transaction(pt_id: int) -> bool:
    """Sletter en planlagt transaktion."""
    repo: IPlannedTransaction = get_planned_transaction_repository()
    return repo.delete(pt_id)