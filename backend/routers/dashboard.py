# backend/routers/dashboard.py

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from datetime import date

from backend.database import get_db
from backend.schemas.dashboard import FinancialOverview

# LØSNING: Importer funktioner direkte fra modulet i stedet for pakken.
from backend.services.dashboard_service import (
    get_financial_overview, # <-- Tilføj de funktioner, routeren bruger
    get_expenses_by_month
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

@router.get("/overview/", response_model=FinancialOverview)
def get_financial_overview_route(
    start_date: Optional[date] = Query(None, description="Startdato (YYYY-MM-DD). Standard er 30 dage tilbage."),
    end_date: Optional[date] = Query(None, description="Slutdato (YYYY-MM-DD). Standard er i dag."),
    db: Session = Depends(get_db)
):
    """
    Henter et finansielt overblik for en given periode.
    """
    try:
        # Kald funktionen direkte
        overview = get_financial_overview(db, start_date, end_date)
        return overview
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Uventet fejl: {e}")


@router.get("/expenses-by-month/", response_model=List[Dict[str, Any]])
def get_expenses_by_month_route(
    start_date: Optional[date] = Query(None, description="Startdato for filtrering (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Slutdato for filtrering (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Henter månedlige udgifter for en given periode, grupperet efter måned og år.
    """
    try:
        # Kald funktionen direkte
        results = get_expenses_by_month(db, start_date, end_date)
        return results
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Uventet fejl: {e}")