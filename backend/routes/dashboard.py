from fastapi import APIRouter, Depends, Query, HTTPException, status, Header
from typing import Dict, List, Any, Optional
from datetime import date

from backend.shared.schemas.dashboard import FinancialOverview
from backend.auth import decode_token, get_current_user_id
from backend.services.dashboard_service import (
    get_financial_overview,
    get_expenses_by_month
)
from backend.repository import get_account_repository

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
) -> Optional[int]:
    """Henter account_id fra X-Account-ID header eller fra user's første account."""
    account_id = None

    if x_account_id:
        try:
            account_id = int(x_account_id)
            return account_id
        except ValueError:
            pass

    if not account_id and authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            account_repo = get_account_repository()
            accounts = account_repo.get_all(user_id=token_data.user_id)
            if accounts:
                account_id = accounts[0]["idAccount"]

    return account_id

@router.get("/overview/", response_model=FinancialOverview)
def get_financial_overview_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    account_id: Optional[int] = Depends(get_account_id_from_headers)
):
    if not account_id:
        raise HTTPException(status_code=400, detail="Account ID mangler. Vælg en konto først.")
    
    overview = get_financial_overview(start_date, end_date, account_id)
    return overview

@router.get("/expenses-by-month/", response_model=List[Dict[str, Any]])
def get_expenses_by_month_route(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    account_id: Optional[int] = Depends(get_account_id_from_headers)
):
    if not account_id:
        raise HTTPException(status_code=400, detail="Account ID mangler. Vælg en konto først.")
    
    results = get_expenses_by_month(start_date, end_date, account_id)
    return results
