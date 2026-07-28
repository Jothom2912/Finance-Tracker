from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.adapters.outbound.enable_banking_client import BankConfigError
from app.dependencies import aclose_banking_client
from app.domain.exceptions import (
    BankAccountNotOwned,
    BankConnectionInactive,
    BankConnectionNotFound,
    BankConsentExpired,
    PendingAuthorizationNotFound,
    ProjectionIntegrityError,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    # Shared Enable Banking AsyncClient holds a connection pool for the
    # process lifetime — release it on shutdown.
    await aclose_banking_client()


app = FastAPI(title="Banking Service", version="1.0.0", lifespan=lifespan)


@app.exception_handler(BankConnectionNotFound)
async def connection_not_found_handler(_request: Request, exc: BankConnectionNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(BankConnectionInactive)
async def connection_inactive_handler(_request: Request, exc: BankConnectionInactive) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(BankConsentExpired)
async def consent_expired_handler(_request: Request, exc: BankConsentExpired) -> JSONResponse:
    logger.warning("Consent expired: %s", exc)
    return JSONResponse(status_code=409, content={"detail": RECONSENT_DETAIL})


@app.exception_handler(BankAccountNotOwned)
async def account_not_owned_handler(_request: Request, exc: BankAccountNotOwned) -> JSONResponse:
    logger.warning("Authorization failure: %s", exc)
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ProjectionIntegrityError)
async def projection_integrity_handler(_request: Request, exc: ProjectionIntegrityError) -> JSONResponse:
    logger.exception("Projection integrity error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal account-reference error"})


@app.exception_handler(PendingAuthorizationNotFound)
async def pending_auth_not_found_handler(_request: Request, exc: PendingAuthorizationNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


# P2-42a.  503, not 500: Enable Banking is an *optional* integration, so a deploy
# without a usable PEM is unavailable-but-correct, not a defect in this service.
# 500 also lies about retryability — and it is retryable here, because
# `_banking_client` stays None when construction raises, so every request tries
# again rather than latching a broken singleton.
#
# This has to be an app-level handler rather than a per-route try/except.  The
# error is raised while FastAPI resolves `Depends(get_banking_service)` ->
# `_get_banking_client()` -> `EnableBankingConfig` / `EnableBankingClient.__init__`,
# i.e. *before* any route body executes.  That is why `GET /connections`, which has
# no try/except at all, returned a bare 500 to the dashboard — and why the
# `except BankConfigError` blocks that used to sit on `/available-banks` and
# `/connect` never fired for a missing PEM either.  They only ever caught config
# errors raised *inside* the service call, such as JWT signing.
#
# WARNING rather than exception(): a missing PEM in a deploy that does not use bank
# sync is an operator fact, not a stack trace worth paging on — same treatment as
# BankConnectionInactive above.  The message carries which config is at fault.
@app.exception_handler(BankConfigError)
async def bank_config_error_handler(_request: Request, exc: BankConfigError) -> JSONResponse:
    logger.warning("Enable Banking not configured — returning 503: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Bank-integrationen er ikke tilgængelig lige nu. Prøv igen senere."},
    )


from app.adapters.inbound.bank_api import RECONSENT_DETAIL  # noqa: E402
from app.adapters.inbound.bank_api import router as bank_router

app.include_router(bank_router, prefix="/api/v1/bank")


@app.get("/health", tags=["Health"])
async def health() -> Response:
    return Response(status_code=200, content='{"status":"ok"}', media_type="application/json")
