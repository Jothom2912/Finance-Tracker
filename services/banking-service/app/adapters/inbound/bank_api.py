from __future__ import annotations

import logging
import uuid
from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.adapters.outbound.enable_banking_client import (
    BankApiUnavailable,
    BankAuthorizationError,
    BankConfigError,
)
from app.application.service import BankingService
from app.auth import get_current_user_id
from app.config import settings
from app.dependencies import get_banking_service
from app.domain.exceptions import (
    BankAccountNotOwned,
    BankConnectionInactive,
    BankConnectionNotFound,
    BankConsentExpired,
    PendingAuthorizationNotFound,
    ProjectionIntegrityError,
)

RECONSENT_DETAIL = (
    "Bankforbindelsens samtykke er udløbet. "
    "Forny adgangen til banken (nyt samtykke) for at kunne synkronisere igen."
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Banking"])


class ConnectRequest(BaseModel):
    bank_name: str
    country: str = "DK"
    account_id: int


class ConnectResponse(BaseModel):
    authorization_url: str
    state: str


class SyncRequest(BaseModel):
    date_from: Optional[str] = None


class SyncSagaResponse(BaseModel):
    saga_id: str
    status: str = "started"


def _callback_redirect(
    status: str,
    *,
    code: str | None = None,
    connections: int | None = None,
    ref: str | None = None,
) -> RedirectResponse:
    params: dict[str, str] = {"status": status}
    if code is not None:
        params["code"] = code
    if connections is not None:
        params["connections"] = str(connections)
    if ref is not None:
        params["ref"] = ref
    url = f"{settings.FRONTEND_URL}/bank/callback?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=303)


# ── JSON endpoints (JWT required) ──────────────────────────────────


@router.get("/available-banks")
async def list_available_banks(
    country: str = Query(default="DK"),
    _user_id: int = Depends(get_current_user_id),
    service: BankingService = Depends(get_banking_service),
) -> list[dict]:
    try:
        return await service.list_banks(country)
    except BankConfigError as exc:
        logger.exception("Enable Banking misconfigured while listing banks")
        raise HTTPException(status_code=500, detail=f"Bank adapter misconfigured: {exc}")
    except BankApiUnavailable as exc:
        logger.exception("Enable Banking upstream error while listing banks")
        raise HTTPException(status_code=502, detail=f"Enable Banking API unavailable: {exc}")


@router.post("/connect", response_model=ConnectResponse)
async def start_bank_connection(
    req: ConnectRequest,
    user_id: int = Depends(get_current_user_id),
    service: BankingService = Depends(get_banking_service),
) -> ConnectResponse:
    try:
        result = await service.start_connect(
            bank_name=req.bank_name,
            country=req.country,
            account_id=req.account_id,
            user_id=user_id,
        )
    except BankAccountNotOwned as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except BankConfigError as exc:
        logger.exception("Enable Banking misconfigured while starting connect")
        raise HTTPException(status_code=500, detail=f"Bank adapter misconfigured: {exc}")
    except BankApiUnavailable as exc:
        logger.exception("Enable Banking upstream error while starting connect")
        raise HTTPException(status_code=502, detail=f"Enable Banking API unavailable: {exc}")
    return ConnectResponse(authorization_url=result["url"], state=result["state"])


# ── OAuth callback (NO JWT — browser redirect from Enable Banking) ─


@router.get("/callback")
async def bank_callback(
    state: str = Query(...),
    auth_code: Optional[str] = Query(default=None, alias="code"),
    error: Optional[str] = Query(default=None),
    service: BankingService = Depends(get_banking_service),
) -> RedirectResponse:
    if error:
        ref = str(uuid.uuid4())[:8]
        logger.error(
            "Bank authorization failed [%s]: error=%s, state=%s",
            ref, error, state,
        )
        return _callback_redirect("error", code="auth_rejected", ref=ref)

    if not auth_code:
        ref = str(uuid.uuid4())[:8]
        logger.warning(
            "Bank callback missing authorization code [%s]: state=%s",
            ref, state,
        )
        return _callback_redirect("error", code="missing_code", ref=ref)

    try:
        connections = await service.complete_connect(
            auth_code=auth_code, state=state,
        )
    except PendingAuthorizationNotFound:
        ref = str(uuid.uuid4())[:8]
        logger.warning(
            "Unknown/expired state in bank callback [%s]: state=%s",
            ref, state,
        )
        return _callback_redirect("error", code="unknown_state", ref=ref)
    except BankAuthorizationError as exc:
        ref = str(uuid.uuid4())[:8]
        logger.warning(
            "Enable Banking rejected auth code [%s]: %s", ref, exc,
        )
        return _callback_redirect("error", code="auth_rejected", ref=ref)
    except BankConfigError:
        ref = str(uuid.uuid4())[:8]
        logger.exception(
            "Enable Banking misconfigured during callback [%s]", ref,
        )
        return _callback_redirect("error", code="config_error", ref=ref)
    except BankApiUnavailable:
        ref = str(uuid.uuid4())[:8]
        logger.exception(
            "Enable Banking upstream error during callback [%s]", ref,
        )
        return _callback_redirect("error", code="upstream_unavailable", ref=ref)
    except Exception:
        # Catch-all: browser is waiting for a redirect — a JSON 500
        # would leave the user stuck on a blank page.
        ref = str(uuid.uuid4())[:8]
        logger.exception(
            "Unexpected error in bank callback [%s]", ref,
        )
        return _callback_redirect("error", code="internal_error", ref=ref)

    return _callback_redirect("success", connections=len(connections))


# ── Authenticated resource endpoints ───────────────────────────────


@router.get("/connections")
async def list_connections(
    account_id: int = Query(...),
    user_id: int = Depends(get_current_user_id),
    service: BankingService = Depends(get_banking_service),
) -> list[dict]:
    return await service.list_connections(account_id, user_id=user_id)


@router.post(
    "/connections/{connection_id}/sync",
    status_code=202,
    response_model=SyncSagaResponse,
)
async def sync_transactions(
    connection_id: UUID,
    req: SyncRequest | None = None,
    user_id: int = Depends(get_current_user_id),
    service: BankingService = Depends(get_banking_service),
) -> SyncSagaResponse:
    date_from = req.date_from if req else None
    try:
        saga_id = await service.start_sync_saga(
            connection_id=connection_id,
            user_id=user_id,
            date_from=date_from,
        )
    except BankConnectionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BankConnectionInactive as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except BankConsentExpired as exc:
        logger.warning("Sync rejected, consent expired: %s", exc)
        raise HTTPException(status_code=409, detail=RECONSENT_DETAIL)
    except ProjectionIntegrityError as exc:
        logger.exception(
            "Account projection missing during sync start (connection=%s)",
            connection_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))
    return SyncSagaResponse(saga_id=saga_id, status="started")


@router.delete("/connections/{connection_id}")
async def disconnect_bank(
    connection_id: UUID,
    user_id: int = Depends(get_current_user_id),
    service: BankingService = Depends(get_banking_service),
) -> dict:
    if not await service.disconnect(connection_id, user_id=user_id):
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"message": "Bank disconnected"}
