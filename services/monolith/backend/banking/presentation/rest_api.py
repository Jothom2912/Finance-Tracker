"""
FastAPI routes for bank connection and transaction sync.

Endpoints:
  GET  /bank/available-banks     - List available banks
  POST /bank/connect             - Start bank authorization
  GET  /bank/callback            - OAuth callback (bank redirects here)
  GET  /bank/connections         - List connected bank accounts
  POST /bank/connections/{id}/sync - Sync transactions from a connection
  DELETE /bank/connections/{id}  - Disconnect a bank
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.banking.adapters.outbound.enable_banking_client import (
    EnableBankingClient,
    EnableBankingConfig,
)
from backend.banking.application.service import BankingService
from backend.category.application.categorization_service import CategorizationService
from backend.database.mysql import get_db
from backend.dependencies import get_categorization_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bank", tags=["Banking"])

# state → account_id mapping (survives across requests within same process)
_pending_authorizations: dict[str, int] = {}

# ──────────────────────────────────────────
# Singleton client (created on first use)
# ──────────────────────────────────────────

_client: EnableBankingClient | None = None


def _get_client() -> EnableBankingClient:
    global _client
    if _client is None:
        import os
        from pathlib import Path

        key_path = os.getenv("ENABLE_BANKING_KEY_PATH", "./enablebanking-privat.pem")
        if not os.path.isabs(key_path):
            # Walk up from rest_api.py until we find the PEM file or hit root
            search = Path(__file__).resolve().parent
            pem_name = key_path.lstrip("./")
            while search != search.parent:
                candidate = search / pem_name
                if candidate.exists():
                    key_path = str(candidate)
                    break
                search = search.parent

        config = EnableBankingConfig(
            app_id=os.getenv("ENABLE_BANKING_APP_ID", ""),
            key_path=key_path,
            redirect_uri=os.getenv("ENABLE_BANKING_REDIRECT_URI", "https://example.com/callback"),
            environment=os.getenv("ENABLE_BANKING_ENVIRONMENT", "sandbox"),
        )
        _client = EnableBankingClient(config)
    return _client


def _get_banking_service(
    db: Session = Depends(get_db),
    categorization_service: CategorizationService = Depends(get_categorization_service),
) -> BankingService:
    return BankingService(
        db=db,
        banking_client=_get_client(),
        categorization_service=categorization_service,
    )


# ──────────────────────────────────────────
# Request/Response models
# ──────────────────────────────────────────


class ConnectRequest(BaseModel):
    bank_name: str
    country: str = "DK"
    account_id: int = 1


class ConnectResponse(BaseModel):
    authorization_url: str
    state: str


class SyncRequest(BaseModel):
    date_from: Optional[str] = None


class SyncResponse(BaseModel):
    total_fetched: int
    new_imported: int
    duplicates_skipped: int
    errors: int


# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────


@router.get("/available-banks")
def list_available_banks(
    country: str = Query(default="DK", description="ISO country code"),
    service: BankingService = Depends(_get_banking_service),
):
    """List available banks for a country."""
    try:
        return service.list_banks(country)
    except Exception as e:
        logger.exception("Failed to list banks")
        raise HTTPException(status_code=502, detail=f"Enable Banking API error: {e}")


@router.post("/connect", response_model=ConnectResponse)
def start_bank_connection(
    req: ConnectRequest,
    service: BankingService = Depends(_get_banking_service),
):
    """Start bank authorization flow. Returns URL to redirect user to."""
    try:
        result = service.start_connect(bank_name=req.bank_name, country=req.country)
        _pending_authorizations[result["state"]] = req.account_id
        return ConnectResponse(authorization_url=result["url"], state=result["state"])
    except Exception as e:
        logger.exception("Failed to start bank connection")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/callback")
def bank_callback(
    state: str = Query(..., description="State parameter from authorization"),
    code: Optional[str] = Query(default=None, description="Authorization code from bank"),
    error: Optional[str] = Query(default=None, description="Error from bank"),
    service: BankingService = Depends(_get_banking_service),
):
    """
    OAuth callback — bank redirects here after user authorization.

    The 'code' and 'state' parameters come from Enable Banking.
    Account ID is resolved via the state mapping stored at /connect time.
    """
    if error:
        logger.error("Bank authorization failed: error=%s, state=%s", error, state)
        raise HTTPException(
            status_code=400,
            detail=f"Bank authorization failed: {error}",
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    account_id = _pending_authorizations.pop(state, None)
    if account_id is None:
        raise HTTPException(
            status_code=400,
            detail="Unknown state parameter. Authorization may have expired — please retry.",
        )

    try:
        connections = service.complete_connect(auth_code=code, account_id=account_id)
        return {
            "message": f"Connected {len(connections)} bank account(s)",
            "connections": connections,
        }
    except Exception as e:
        logger.exception("Failed to complete bank connection")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/connections")
def list_connections(
    account_id: int = Query(..., description="Internal account ID"),
    service: BankingService = Depends(_get_banking_service),
):
    """List all bank connections for an account."""
    return service.list_connections(account_id)


@router.post("/connections/{connection_id}/sync", response_model=SyncResponse)
def sync_transactions(
    connection_id: int,
    req: SyncRequest = None,
    service: BankingService = Depends(_get_banking_service),
):
    """Sync transactions from a connected bank account."""
    try:
        date_from = req.date_from if req else None
        result = service.sync_transactions(connection_id=connection_id, date_from=date_from)
        return SyncResponse(
            total_fetched=result.total_fetched,
            new_imported=result.new_imported,
            duplicates_skipped=result.duplicates_skipped,
            errors=result.errors,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to sync transactions")
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/connections/{connection_id}")
def disconnect_bank(
    connection_id: int,
    service: BankingService = Depends(_get_banking_service),
):
    """Disconnect a bank connection."""
    if not service.disconnect(connection_id):
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"message": "Bank disconnected"}
