from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from typing import List, Optional, Annotated

# VIGTIGT: Importér Service laget og dine Pydantic Skemaer
from backend.database import get_db
from backend.shared.schemas.budget import BudgetCreate, BudgetUpdate, BudgetInDB as BudgetSchema, BudgetSummary
from backend.auth import decode_token

# KORREKT: Direkte import af funktionerne
from backend.services.budget_service import (
    get_budgets_by_period,
    get_budget_by_id,
    create_budget,
    update_budget,
    delete_budget,
    get_budget_summary
)

router = APIRouter(
    prefix="/budgets",
    tags=["Budgets"],
    responses={404: {"description": "Not found"}},
)

def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
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
            accounts = account_service.get_accounts_by_user( token_data.user_id)
            if accounts:
                account_id = accounts[0].idAccount

    return account_id

# --- Hentning af Budgetter (Filtreret af måned/år/konto) ---
@router.get("/", response_model=List[BudgetSchema])
async def get_budgets_for_account(
    month: Optional[str] = Query(None, description="Month filter (MM format)"),
    year: Optional[str] = Query(None, description="Year filter (YYYY format)"),
    account_id: Optional[int] = Depends(get_account_id_from_headers)
):
    """
    Retrieve all budgets for a specific account.
    """
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # RETTET: Kald funktionen direkte
    budgets = get_budgets_by_period( account_id=account_id, start_date=None, end_date=None)
    return budgets


# --- Budget Opsummering ---
# VIGTIGT: Denne route skal være FØR /{budget_id} for at undgå route-konflikt
@router.get("/summary", response_model=BudgetSummary)
async def get_budget_summary_route(
    month: Annotated[str, Query(..., description="Month (1-12).")],
    year: Annotated[str, Query(..., description="Year (YYYY format).")],
    account_id: Optional[int] = Depends(get_account_id_from_headers)
):
    """
    Generates a detailed budget summary for a specific account, month, and year.
    """
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # Konverter og valider month og year
    try:
        month_int = int(month)
        year_int = int(year)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ugyldige værdier: month og year skal være heltal. Fik month={month} (type: {type(month).__name__}), year={year} (type: {type(year).__name__})"
        )

    # Valider ranges
    if month_int < 1 or month_int > 12:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Month skal være mellem 1 og 12. Fik: {month_int}"
        )

    if year_int < 2000 or year_int > 9999:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Year skal være mellem 2000 og 9999. Fik: {year_int}"
        )

    # Kald funktionen direkte
    summary = get_budget_summary( account_id, month_int, year_int)
    return summary


# --- Hentning af et specifikt Budget ---
@router.get("/{budget_id}", response_model=BudgetSchema)
async def get_budget_by_id_route( # Omdøbt for at undgå navnekonflikt
    budget_id: int
):
    """
    Retrieve details for a specific budget by its ID.
    """
    # RETTET: Kald funktionen direkte
    budget = get_budget_by_id(budget_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


# --- Oprettelse af Budget ---
@router.post("/", response_model=BudgetSchema, status_code=status.HTTP_201_CREATED)
async def create_budget_route(
    budget: BudgetCreate,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID")
):
    """
    Create a new budget.
    """
    # Hent account_id fra header eller fra user's første account
    account_id = None
    if x_account_id:
        try:
            account_id = int(x_account_id)
        except ValueError:
            pass

    # Hvis ingen account_id i header, find første account for brugeren
    if not account_id and authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        token_data = decode_token(token)
        if token_data:
            from backend.services import account_service
            accounts = account_service.get_accounts_by_user( token_data.user_id)
            if accounts:
                account_id = accounts[0]["idAccount"]

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # Set account_id on budget if not already set
    if budget.Account_idAccount is None:
        budget = budget.model_copy(update={"Account_idAccount": account_id})

    try:
        # Call service function directly
        new_budget = create_budget(budget)
        return new_budget
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not create budget: {str(e)}")


# --- Opdatering af Budget ---
@router.put("/{budget_id}", response_model=BudgetSchema)
async def update_budget_route(budget_id: int, budget: BudgetUpdate):
    """
    Update an existing budget.
    """
     # Call service function directly
    updated_budget = update_budget(budget_id, budget)
    return updated_budget


# --- Sletning af Budget ---
@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_route(budget_id: int):
    """
    Delete a specific budget.
    """
    # RETTET: Kald funktionen direkte
    if not delete_budget(budget_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return