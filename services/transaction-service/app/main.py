from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.inbound.rest_api import planned_router, transaction_router
from app.config import settings
from app.domain.exceptions import (
    CSVImportException,
    InvalidTransactionException,
    PlannedTransactionNotFoundException,
    TransactionNotFoundException,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Transaction Service",
    version="0.2.0",
    description="Handles financial transactions and planned transactions. "
    "Domain events are persisted via transactional outbox and "
    "published by a separate worker process.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


app.include_router(transaction_router)
app.include_router(planned_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "transaction-service"}
