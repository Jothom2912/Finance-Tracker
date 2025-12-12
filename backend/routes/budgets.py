from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.orm import Session
from typing import List, Optional

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

# --- Hentning af Budgetter (Filtreret af måned/år/konto) ---
@router.get("/", response_model=List[BudgetSchema])
async def get_budgets_for_account(
    month: Optional[str] = Query(None, description="Month filter (MM format)"),
    year: Optional[str] = Query(None, description="Year filter (YYYY format)"),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
    db: Session = Depends(get_db)
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
    budgets = get_budgets_by_period(db, account_id=account_id, start_date=None, end_date=None)
    return budgets


# --- Hentning af et specifikt Budget ---
@router.get("/{budget_id}", response_model=BudgetSchema)
async def get_budget_by_id_route( # Omdøbt for at undgå navnekonflikt
    budget_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieve details for a specific budget by its ID.
    """
    # RETTET: Kald funktionen direkte
    budget = get_budget_by_id(db, budget_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


# --- Oprettelse af Budget ---
@router.post("/", response_model=BudgetSchema, status_code=status.HTTP_201_CREATED)
async def create_budget_route(
    budget: BudgetCreate,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
    db: Session = Depends(get_db)
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
            accounts = account_service.get_accounts_by_user(db, token_data.user_id)
            if accounts:
                account_id = accounts[0].idAccount

    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # Tilføj account_id til budget data hvis det ikke allerede er sat
    budget_dict = budget.model_dump()

    # Konverter month/year til budget_date hvis budget_date ikke er sat
    if not budget_dict.get('budget_date'):
        month = budget_dict.get('month')
        year = budget_dict.get('year')
        if month and year:
            try:
                from datetime import date
                budget_dict['budget_date'] = date(int(year), int(month), 1)
            except (ValueError, TypeError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ugyldig måned/år: {month}/{year}"
                )

    # Fjern month/year fra dict da de ikke er i modellen
    budget_dict.pop('month', None)
    budget_dict.pop('year', None)

    if 'Account_idAccount' not in budget_dict or budget_dict.get('Account_idAccount') is None:
        budget_dict['Account_idAccount'] = account_id

    # Opret ny BudgetCreate med account_id
    budget_with_account = BudgetCreate(**budget_dict)

    try:
        # RETTET: Kald funktionen direkte
        new_budget = create_budget(db, budget_with_account)
        return new_budget
    except ValueError as e:
        if "Integritetsfejl" in str(e) or "ugyldig" in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create budget.")


# --- Opdatering af Budget ---
@router.put("/{budget_id}", response_model=BudgetSchema)
async def update_budget_route(budget_id: int, budget: BudgetUpdate, db: Session = Depends(get_db)):
    """
    Update an existing budget.
    """
    try:
        # Konverter month/year til budget_date hvis budget_date ikke er sat
        budget_dict = budget.model_dump(exclude_unset=True)
        if not budget_dict.get('budget_date'):
            month = budget_dict.get('month')
            year = budget_dict.get('year')
            if month and year:
                try:
                    from datetime import date
                    budget_dict['budget_date'] = date(int(year), int(month), 1)
                except (ValueError, TypeError) as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ugyldig måned/år: {month}/{year}"
                    )

        # Fjern month/year fra dict
        budget_dict.pop('month', None)
        budget_dict.pop('year', None)

        # Opret BudgetUpdate med konverteret data
        budget_with_date = BudgetUpdate(**budget_dict)

        # RETTET: Kald funktionen direkte
        updated_budget = update_budget(db, budget_id, budget_with_date)
        if not updated_budget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
        return updated_budget
    except ValueError as e:
          raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during update.")


# --- Sletning af Budget ---
@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_route(budget_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific budget.
    """
    # RETTET: Kald funktionen direkte
    if not delete_budget(db, budget_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return


# --- Budget Opsummering ---
@router.get("/summary", response_model=BudgetSummary)
async def get_budget_summary_route(
    month: int = Query(..., description="Month in MM format (e.g., 1).", ge=1, le=12),
    year: int = Query(..., description="Year in YYYY format (e.g., 2024).", ge=2000),
    account_id: Optional[int] = Depends(get_account_id_from_headers),
    db: Session = Depends(get_db)
):
    """
    Generates a detailed budget summary for a specific account, month, and year.
    """
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account ID mangler. Vælg en konto først."
        )

    # RETTET: Kald funktionen direkte
    summary = get_budget_summary(db, account_id, month, year)
    return summary