"""Internal API endpoints for service-to-service communication."""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.outbound.postgresql_account_repository import PostgresAccountRepository
from app.config import INTERNAL_API_KEY
from app.database import get_db

router = APIRouter(
    prefix="/internal/accounts",
    tags=["Internal"],
)


def _verify_internal_key(
    x_internal_api_key: str = Header(..., alias="x-internal-api-key"),
) -> None:
    """Verify the internal API key for service-to-service calls."""
    if not INTERNAL_API_KEY or x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key.",
        )


@router.get("/{account_id}/exists")
def account_exists(
    account_id: int,
    _: None = Depends(_verify_internal_key),
    db: Session = Depends(get_db),
) -> dict:
    """Check if an account exists. Used by other services (e.g. goal-service)."""
    repo = PostgresAccountRepository(db)
    account = repo.get_by_id(account_id)
    return {"exists": account is not None}


@router.get("/{account_id}/owner")
def account_owner(
    account_id: int,
    _: None = Depends(_verify_internal_key),
    db: Session = Depends(get_db),
) -> dict:
    """Return the owning user_id for an account. Used by goal-service for authorization."""
    repo = PostgresAccountRepository(db)
    account = repo.get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return {"user_id": account.user_id, "account_name": account.name}
