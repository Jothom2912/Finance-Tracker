from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.enable_banking_client import BankConfigError
from app.database import get_db
from app.dependencies import aclose_banking_client, get_banking_client
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
# `get_banking_client()` -> `EnableBankingConfig` / `EnableBankingClient.__init__`,
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


async def _check_database(session: AsyncSession) -> dict[str, Any]:
    """Required dependency: no request this service serves works without it."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        # Deliberately broad. SQLAlchemy wraps driver failures in several
        # unrelated types (OperationalError, InterfaceError, and bare OSError
        # from DNS), and a readiness probe that itself 500s tells an operator
        # nothing. Logged rather than swallowed.
        logger.warning("Readiness: database unreachable: %r", exc)
        return {"ok": False, "error": repr(exc)}
    return {"ok": True}


def _check_enable_banking() -> dict[str, Any]:
    """
    Optional dependency: construct the client and report, never raise.

    `BankConfigError` must be caught *here*.  Letting it reach the app-level
    handler above would return 503 for the whole of /ready and make this
    optional dependency look required — the exact opposite of P2-42a's
    decision that a deploy without a PEM is unavailable-but-correct.

    One call covers all three failure modes: EnableBankingConfig.__post_init__
    validates app_id and that the PEM exists, and __init__ reads the bytes and
    smoke-signs an RS256 JWT with them.

    Honest limit: the client is a process-wide singleton, so this proves
    *constructibility*, not that the PEM is still on disk.  After the first
    success, deleting the file will not turn this degraded.  That is inherent —
    the PEM is only ever read once — and it means this catches a
    misconfigured deploy, not a file that vanishes at runtime.
    """
    try:
        get_banking_client()
    except BankConfigError as exc:
        logger.warning("Readiness: Enable Banking not configured: %s", exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


# P2-42b.  /health proves the process is alive; this proves its dependencies
# are reachable.  banking answered /health 200 through an entire CI run in
# which every bank route 500'd, because the PEM is only read when the client is
# constructed, per request — see
# dev-notes/findings/2026-07-28-banking-service-dead-in-ci.md.
#
# Two levels in one endpoint, because the two dependencies are not the same
# kind of thing:
#
#   database       required  -> 503 + "unavailable"
#   enable_banking optional  -> 200 + "degraded"
#
# Enable Banking must NOT be able to make this pod unready.  If it could, k8s
# would pull a pod out of service over an integration the deploy may not use,
# and a stack without bank sync would never come up at all.
#
# The CI gate is deliberately stricter than this probe: it requires
# status == "ready", because CI *does* use bank sync (P2-39 generates a PEM for
# exactly that), so degraded is a failure there.  The probe answers "can this
# pod take traffic"; the gate answers "is this stack fully configured".
#
# NOT wired into the compose healthcheck or the k8s readinessProbe in this
# item — both currently point at /health, and moving readiness would be the
# first time readiness and liveness diverge in this repo.  That changes traffic
# routing and needs its own verification.  Nothing kept banking-specific here
# beyond the check list, so it can be lifted to services/shared/ unchanged.
@app.get("/ready", tags=["Health"])
async def ready(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    dependencies = {
        "database": await _check_database(session),
        "enable_banking": _check_enable_banking(),
    }
    if not dependencies["database"]["ok"]:
        status, code = "unavailable", 503
    elif not dependencies["enable_banking"]["ok"]:
        status, code = "degraded", 200
    else:
        status, code = "ready", 200
    return JSONResponse(status_code=code, content={"status": status, "dependencies": dependencies})
