from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.adapters.inbound.rest_api import router as analytics_router
from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.client import create_es_client
from app.config import settings
from app.domain.exceptions import (
    AccountNotFoundError,
    InvalidPeriodError,
    ReadStoreUnavailableError,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Fail-fast hvis ES er nede ved opstart: compose/k8s venter på healthy
    # ES, og en app uden read-store kan alligevel intet svare.
    es = create_es_client(settings)
    await ensure_indices(es, settings.es_index_prefix)
    app.state.es = es
    try:
        yield
    finally:
        await es.close()


app = FastAPI(title="Analytics Service", version="0.1.0", lifespan=lifespan)
app.include_router(analytics_router)


@app.exception_handler(AccountNotFoundError)
async def account_not_found_handler(request: Request, exc: AccountNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidPeriodError)
async def invalid_period_handler(request: Request, exc: InvalidPeriodError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ReadStoreUnavailableError)
async def read_store_unavailable_handler(request: Request, exc: ReadStoreUnavailableError) -> JSONResponse:
    logger.warning("Read-store utilgængelig: %s", exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "analytics-service"}
