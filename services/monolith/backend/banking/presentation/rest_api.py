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
import os
import uuid
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.banking.adapters.outbound.enable_banking_client import (
    BankApiUnavailable,
    BankAuthorizationError,
    BankConfigError,
    EnableBankingClient,
    EnableBankingConfig,
)
from backend.banking.adapters.outbound.transaction_service_client import (
    TransactionServiceError,
)
from backend.banking.application.service import BankingService
from backend.banking.domain.exceptions import (
    BankAccountReferenceInvalid,
    BankConnectionInactive,
    BankConnectionNotFound,
)
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

_BANKING_ENV_VARS = (
    "ENABLE_BANKING_APP_ID",
    "ENABLE_BANKING_KEY_PATH",
    "ENABLE_BANKING_REDIRECT_URI",
)

_client: EnableBankingClient | None = None


def _resolve_key_path(raw: str) -> str:
    """Resolve a potentially relative PEM path by walking up from this file."""
    from pathlib import Path as _Path

    if os.path.isabs(raw):
        return raw
    search = _Path(__file__).resolve().parent
    pem_name = raw.lstrip("./")
    while search != search.parent:
        candidate = search / pem_name
        if candidate.exists():
            return str(candidate)
        search = search.parent
    return raw


def validate_banking_config() -> None:
    """Check Enable Banking configuration at startup.

    Three possible states:

    * **All absent** — no ``ENABLE_BANKING_*`` vars set.  Banking is
      disabled; log info and return.  Legitimate for devs who don't
      use the bank integration.
    * **Partial** — some vars set, others missing.  Almost certainly a
      half-finished deploy.  Raise ``BankConfigError`` so the caller
      can log an error.
    * **Fully configured** — validate PEM readability.  Wraps any IO
      error into ``BankConfigError`` so the caller only catches domain
      exceptions.
    """
    configured = {
        var: bool(os.getenv(var, "").strip())
        for var in _BANKING_ENV_VARS
    }

    if not any(configured.values()):
        logger.info("Banking not configured (no ENABLE_BANKING_* vars), bank routes disabled")
        return

    missing = [var for var, present in configured.items() if not present]
    if missing:
        raise BankConfigError(
            f"Partial banking config — set all or none. Missing: {', '.join(missing)}"
        )

    key_path = os.getenv("ENABLE_BANKING_KEY_PATH", "")
    resolved = _resolve_key_path(key_path)
    try:
        with open(resolved, "rb") as f:
            f.read(1)
    except (OSError, FileNotFoundError) as exc:
        raise BankConfigError(f"PEM file unreadable at {resolved}: {exc}") from exc

    logger.info("Banking configured OK (app_id set, PEM readable)")


def _get_client() -> EnableBankingClient:
    global _client
    if _client is None:
        key_path = _resolve_key_path(
            os.getenv("ENABLE_BANKING_KEY_PATH", "./enablebanking-privat.pem")
        )
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
    parse_skipped: int = 0


# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────


# ──────────────────────────────────────────
# Adapter error → HTTP mapping
# ──────────────────────────────────────────
#
# Three typed exceptions from ``enable_banking_client`` map to three
# HTTP status codes with distinct operational meanings.  The mapping
# is deliberately shared across every route that talks to the
# adapter so a reviewer can read the contract in one place instead of
# tracing each ``except`` clause:
#
#   BankConfigError       → 500  our deploy is wrong (missing key, bad JWT)
#   BankAuthorizationError → 400  caller's auth_code is rejected
#   BankApiUnavailable    → 502  Enable Banking is unreachable / 5xx
#
# Anything else propagates.  A ``RuntimeError`` surfacing here is a
# bug by definition — it lands as an uncatalogued 500 with a
# stacktrace in logs, which is what we want operationally.  The
# positive-control test in ``tests/integration/test_bank_sync_routes``
# locks this behaviour in for every route.


@router.get("/available-banks")
def list_available_banks(
    country: str = Query(default="DK", description="ISO country code"),
    service: BankingService = Depends(_get_banking_service),
):
    """List available banks for a country."""
    try:
        return service.list_banks(country)
    except BankConfigError as exc:
        logger.exception("Enable Banking misconfigured while listing banks")
        raise HTTPException(status_code=500, detail=f"Bank adapter misconfigured: {exc}")
    except BankApiUnavailable as exc:
        logger.exception("Enable Banking upstream error while listing banks")
        raise HTTPException(status_code=502, detail=f"Enable Banking API unavailable: {exc}")


@router.post("/connect", response_model=ConnectResponse)
def start_bank_connection(
    req: ConnectRequest,
    service: BankingService = Depends(_get_banking_service),
):
    """Start bank authorization flow. Returns URL to redirect user to.

    Exception mapping follows the same principle as ``sync_transactions``:
    only known typed errors are mapped; anything uncatalogued propagates
    to FastAPI's 500 handler.  ``BankAuthorizationError`` cannot be
    raised here (no user-supplied ``auth_code`` is involved yet) so only
    the config/upstream pair is handled.
    """
    try:
        result = service.start_connect(bank_name=req.bank_name, country=req.country)
    except BankConfigError as exc:
        logger.exception("Enable Banking misconfigured while starting connect flow")
        raise HTTPException(status_code=500, detail=f"Bank adapter misconfigured: {exc}")
    except BankApiUnavailable as exc:
        logger.exception("Enable Banking upstream error while starting connect flow")
        raise HTTPException(status_code=502, detail=f"Enable Banking API unavailable: {exc}")

    _pending_authorizations[result["state"]] = req.account_id
    return ConnectResponse(authorization_url=result["url"], state=result["state"])


def _get_frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


def _callback_redirect(
    status: str,
    *,
    code: str | None = None,
    connections: int | None = None,
    ref: str | None = None,
) -> RedirectResponse:
    """Build a redirect to the frontend bank callback page.

    Only short, fixed error codes are forwarded — never raw exception
    text, which could leak internals or create an XSS surface if the
    frontend renders it carelessly.
    """
    params: dict[str, str] = {"status": status}
    if code is not None:
        params["code"] = code
    if connections is not None:
        params["connections"] = str(connections)
    if ref is not None:
        params["ref"] = ref
    url = f"{_get_frontend_url()}/bank/callback?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=303)


@router.get("/callback")
def bank_callback(
    state: str = Query(..., description="State parameter from authorization"),
    auth_code: Optional[str] = Query(default=None, alias="code", description="Authorization code from bank"),
    error: Optional[str] = Query(default=None, description="Error from bank"),
    service: BankingService = Depends(_get_banking_service),
):
    """
    OAuth callback — bank redirects here after user authorization.

    The 'code' and 'state' parameters come from Enable Banking.
    Account ID is resolved via the state mapping stored at /connect time.

    On any outcome (success or failure) this endpoint redirects to the
    frontend ``/bank/callback`` page with a short error code rather than
    rendering raw JSON.  Full exception detail is logged server-side
    with a correlation ref the frontend can display for support.
    """
    if error:
        ref = str(uuid.uuid4())[:8]
        logger.error("Bank authorization failed [%s]: error=%s, state=%s", ref, error, state)
        return _callback_redirect("error", code="auth_rejected", ref=ref)

    if not auth_code:
        ref = str(uuid.uuid4())[:8]
        logger.warning("Bank callback missing authorization code [%s]: state=%s", ref, state)
        return _callback_redirect("error", code="missing_code", ref=ref)

    account_id = _pending_authorizations.pop(state, None)
    if account_id is None:
        ref = str(uuid.uuid4())[:8]
        logger.warning("Unknown state parameter in bank callback [%s]: state=%s", ref, state)
        return _callback_redirect("error", code="unknown_state", ref=ref)

    try:
        connections = service.complete_connect(auth_code=auth_code, account_id=account_id)
    except BankAuthorizationError as exc:
        ref = str(uuid.uuid4())[:8]
        logger.warning("Enable Banking rejected authorization code [%s]: %s", ref, exc)
        return _callback_redirect("error", code="auth_rejected", ref=ref)
    except BankConfigError:
        ref = str(uuid.uuid4())[:8]
        logger.exception("Enable Banking misconfigured during callback [%s]", ref)
        return _callback_redirect("error", code="config_error", ref=ref)
    except BankApiUnavailable:
        ref = str(uuid.uuid4())[:8]
        logger.exception("Enable Banking upstream error during callback [%s]", ref)
        return _callback_redirect("error", code="upstream_unavailable", ref=ref)

    return _callback_redirect("success", connections=len(connections))


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
    """Sync transactions from a connected bank account.

    Exception mapping is deliberately restricted to known domain
    failures.  Anything else — including unexpected ``ValueError`` or
    other uncaught exceptions — propagates to Starlette's default
    server-error handler and surfaces as an HTTP 500.

    Why no ``except Exception`` as a safety net: a catch-all absorbs
    bugs into a plausible-looking status code, which pushes the real
    diagnosis into log-archaeology after the fact.  A 500 with a
    stacktrace tells the operator *this is ours and it is unexpected*
    in one hop; a laundered 502 tells them nothing and hides the
    class of error.  ``tests/integration/test_bank_sync_routes.py``
    contains a positive-control test (``RuntimeError`` → 500) that
    goes red the moment a reviewer reintroduces a catch-all here —
    that is the operational guarantee that this principle stays in
    force.
    """
    date_from = req.date_from if req else None
    try:
        result = service.sync_transactions(connection_id=connection_id, date_from=date_from)
    except BankConnectionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BankConnectionInactive as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except BankAccountReferenceInvalid as exc:
        logger.exception(
            "Referential integrity error on bank sync (connection=%d)",
            connection_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal account-reference error: {exc}",
        )
    except TransactionServiceError as exc:
        logger.exception(
            "transaction-service unavailable during bank sync (connection=%d)",
            connection_id,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Upstream transaction-service error: {exc}",
        )

    return SyncResponse(
        total_fetched=result.total_fetched,
        new_imported=result.new_imported,
        duplicates_skipped=result.duplicates_skipped,
        errors=result.errors,
        parse_skipped=result.parse_skipped,
    )


@router.delete("/connections/{connection_id}")
def disconnect_bank(
    connection_id: int,
    service: BankingService = Depends(_get_banking_service),
):
    """Disconnect a bank connection."""
    if not service.disconnect(connection_id):
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"message": "Bank disconnected"}
