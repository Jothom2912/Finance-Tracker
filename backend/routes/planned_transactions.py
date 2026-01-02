from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from backend.database import get_db
from backend.shared.schemas.planned_transactions import PlannedTransactions as PTSchema, PlannedTransactionsCreate, PlannedTransactionsBase
from backend.services import planned_transactions_service

router = APIRouter(
    prefix="/planned-transactions",
    tags=["Planned Transactions"],
)

@router.post("/", response_model=PTSchema, status_code=status.HTTP_201_CREATED)
def create_pt_route(pt_data: PlannedTransactionsCreate):
    """Opretter en ny planlagt transaktion."""
    try:
        db_pt = planned_transactions_service.create_planned_transaction(pt_data)
        return db_pt
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[PTSchema])
def read_pts_route(skip: int = 0, limit: int = 100):
    """Henter en liste over planlagte transaktioner."""
    return planned_transactions_service.get_planned_transactions( skip=skip, limit=limit)

@router.get("/{pt_id}", response_model=PTSchema)
def read_pt_route(pt_id: int):
    """Henter en planlagt transaktion baseret på ID."""
    db_pt = planned_transactions_service.get_planned_transaction_by_id(pt_id)
    if db_pt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planlagt transaktion ikke fundet.")
    return db_pt

@router.put("/{pt_id}", response_model=PTSchema)
def update_pt_route(pt_id: int, pt_data: PlannedTransactionsBase):
    """Opdaterer en planlagt transaktion."""
    try:
        updated_pt = planned_transactions_service.update_planned_transaction(pt_id, pt_data)
        if updated_pt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planlagt transaktion ikke fundet.")
        return updated_pt
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))