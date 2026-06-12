from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.domain.exceptions import (
    BankAccountNotOwned,
    BankConnectionInactive,
    BankConnectionNotFound,
    PendingAuthorizationNotFound,
    ProjectionIntegrityError,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Banking Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BankConnectionNotFound)
async def connection_not_found_handler(_request: Request, exc: BankConnectionNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(BankConnectionInactive)
async def connection_inactive_handler(_request: Request, exc: BankConnectionInactive) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


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


from app.adapters.inbound.bank_api import router as bank_router

app.include_router(bank_router, prefix="/api/v1/bank")


@app.get("/health", tags=["Health"])
async def health() -> Response:
    return Response(status_code=200, content='{"status":"ok"}', media_type="application/json")
