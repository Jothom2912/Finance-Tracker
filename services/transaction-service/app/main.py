from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from observability import setup_logging

from app.adapters.inbound.rest_api import planned_router, transaction_router
from app.config import settings
from app.domain.exceptions import (
    CSVImportException,
    InvalidTransactionException,
    PlannedTransactionNotFoundException,
    SubcategoryMismatchException,
    SubcategoryNotFoundException,
    TransactionNotFoundException,
)

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Transaction Service",
    version="0.2.0",
    description="Handles financial transactions and planned transactions. "
    "Domain events are persisted via transactional outbox and "
    "published by a separate worker process.",
)


@app.middleware("http")
async def reject_oversized_body(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Reject an oversized POST before its body is spooled to disk (P2-29).

    This is the *second* of two layers, and it buys something the handler
    guard in ``rest_api.py`` cannot: by the time a handler runs, FastAPI has
    already parsed the multipart body, so the payload is sitting in ``/tmp``.
    Rejecting on the declared ``Content-Length`` happens before that write.
    Browsers always set the header for ``FormData``, so this covers the real
    client.

    Deliberately NOT stream-counting the body. A hand-rolled client using
    chunked transfer with no ``Content-Length`` still gets to fill ``/tmp`` —
    accepted knowingly: that is bounded by the container's disk and survives a
    restart, whereas the OOM the handler guard prevents kills the process for
    every user. Closing it would mean consuming and re-emitting the body here,
    and rejecting before the body is read makes some clients report
    ECONNRESET instead of surfacing a readable 413.

    Method-scoped rather than route-scoped on purpose: it must not become a
    general body limit for the JSON endpoints, which have their own DTO bounds.
    """
    if request.method == "POST":
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                # Malformed header — let the ASGI server and the handler guard
                # deal with it rather than inventing a status code here.
                length = 0
            if length > settings.CSV_MAX_BYTES:
                limit_mib = settings.CSV_MAX_BYTES // (1024 * 1024)
                logger.warning(
                    "Rejected oversized POST to %s: %d bytes declared, limit %d",
                    request.url.path,
                    length,
                    settings.CSV_MAX_BYTES,
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Forespørgslen er for stor (grænsen er {limit_mib} MB)."},
                )
    return await call_next(request)


@app.exception_handler(TransactionNotFoundException)
async def transaction_not_found_handler(_request: Request, exc: TransactionNotFoundException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PlannedTransactionNotFoundException)
async def planned_not_found_handler(_request: Request, exc: PlannedTransactionNotFoundException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidTransactionException)
async def invalid_transaction_handler(_request: Request, exc: InvalidTransactionException) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(CSVImportException)
async def csv_import_handler(_request: Request, exc: CSVImportException) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(SubcategoryNotFoundException)
async def subcategory_not_found_handler(_request: Request, exc: SubcategoryNotFoundException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(SubcategoryMismatchException)
async def subcategory_mismatch_handler(_request: Request, exc: SubcategoryMismatchException) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# Category CRUD lives in categorization-service per ADR-003 — this
# service holds only event-synced read copies of the taxonomy.
app.include_router(transaction_router)
app.include_router(planned_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "transaction-service"}
