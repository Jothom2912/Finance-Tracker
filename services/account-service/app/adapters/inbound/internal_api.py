"""Internal API endpoints for service-to-service communication."""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.outbound.postgresql_account_repository import PostgresAccountRepository
from app.config import INTERNAL_API_KEY
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal/accounts",
    tags=["Internal"],
)


def _verify_internal_key(
    x_internal_api_key: str = Header(..., alias="x-internal-api-key"),
) -> None:
    """Verify the internal API key for service-to-service calls.

    P3-59: de to grene er delt fordi den ene 403 dækkede to årsager med modsatte ejere —
    vores egen manglende konfiguration og en callers forkerte nøgle.  Responsen er
    bevidst uændret (samme 403, samme body): en caller skal fortsat ikke kunne aflæse
    *hvorfor* nøglen blev afvist.  Det er loggen der får forskellen.

    Målt i step 1: *manglende* header rammer aldrig hertil.  `Header(...)` er uden default,
    så Pydantic afviser med 422 før denne funktion kører.  Grenene nedenfor dækker derfor
    forkert nøgle og ikke-konfigureret nøgle — ikke fravær.
    """
    if not INTERNAL_API_KEY:
        # `error`: vores fejl, ikke callerens.  Uden nøglen afvises *hver* intern request,
        # så goal-services ejerskabstjek fejler konsistent — og gør det i dag i tavshed,
        # hvor det ligner at kontoen ikke findes.
        logger.error("INTERNAL_API_KEY er ikke sat i account-service — alle interne kald afvises med 403")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key.",
        )

    if x_internal_api_key != INTERNAL_API_KEY:
        # `warning`: nøglen gjorde sit arbejde.  Værdien der blev sendt logges ALDRIG — en
        # afvist nøgle kan være den rigtige nøgle fra et andet miljø, og loggen er et
        # dårligere sted at opbevare den end afsenderen.
        logger.warning("Intern request afvist: forkert X-Internal-API-Key")
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
        # P3-59, fravalg: 404'en er entydig — goal-service spurgte om et konto-id der ikke
        # findes, og det er samtidig den normale måde at få det svar på.  En linje her ville
        # fyre ved helt almindelig brug.  Samme afgørelse som `/{account_id}/exists`, der
        # svarer `{"exists": false}` uden at nogen kalder det en fejl.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return {"user_id": account.user_id, "account_name": account.name}
