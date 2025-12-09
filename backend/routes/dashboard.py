# backend/routers/dashboard.py

from fastapi import APIRouter, Depends, Query, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from datetime import date

from backend.database import get_db
from backend.shared.schemas.dashboard import FinancialOverview
from backend.auth import decode_token

# LØSNING: Importer funktioner direkte fra modulet i stedet for pakken.
from backend.services.dashboard_service import (
    get_financial_overview, # <-- Tilføj de funktioner, routeren bruger
    get_expenses_by_month
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db)
) -> Optional[int]:
    """Henter account_id fra X-Account-ID header eller fra user's første account."""
    account_id = None
    
    # Først prøv at hente fra X-Account-ID header
    if x_account_id:
        try:
            account_id = int(x_account_id)
            return account_id
        except ValueError:
            pass
    
    # Hvis ikke fundet, prøv at hente fra user's første account
    if not account_id and authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            from backend.services import account_service
            accounts = account_service.get_accounts_by_user(db, token_data.user_id)
            if accounts:
                account_id = accounts[0].idAccount
    
    return account_id

@router.get("/overview/", response_model=FinancialOverview)
def get_financial_overview_route(
    start_date: Optional[date] = Query(None, description="Startdato (YYYY-MM-DD). Standard er 30 dage tilbage."),
    end_date: Optional[date] = Query(None, description="Slutdato (YYYY-MM-DD). Standard er i dag."),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
    db: Session = Depends(get_db)
):
    """
    Henter et finansielt overblik for en given periode.
    """
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )
    
    try:
        # Kald funktionen direkte med account_id
        overview = get_financial_overview(db, start_date, end_date, account_id)
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