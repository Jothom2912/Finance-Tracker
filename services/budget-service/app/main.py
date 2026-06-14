from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis

from app.adapters.inbound.monthly_budget_api import router as monthly_budget_router
from app.adapters.inbound.rest_api import router
from app.config import settings
from app.domain.exceptions import (
    AccountRequiredForBudget,
    BudgetNotFound,
    CategoryNotFoundForBudget,
    CategoryRequiredForBudget,
    MonthlyBudgetAlreadyClosed,
    MonthlyBudgetAlreadyExists,
    MonthlyBudgetException,
    MonthlyBudgetNotFound,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = aioredis.from_url("redis://redis:6379")

    FastAPICache.init(
        RedisBackend(redis),
        prefix="budget-service",
    )

    yield


app = FastAPI(
    title="Budget Service",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BudgetNotFound)
async def budget_not_found_handler(_request: Request, exc: BudgetNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(AccountRequiredForBudget)
async def account_required_handler(_request: Request, exc: AccountRequiredForBudget) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(CategoryRequiredForBudget)
async def category_required_handler(_request: Request, exc: CategoryRequiredForBudget) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(CategoryNotFoundForBudget)
async def category_not_found_handler(_request: Request, exc: CategoryNotFoundForBudget) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(MonthlyBudgetNotFound)
async def monthly_budget_not_found_handler(_request: Request, exc: MonthlyBudgetNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(MonthlyBudgetAlreadyExists)
async def monthly_budget_exists_handler(_request: Request, exc: MonthlyBudgetAlreadyExists) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(MonthlyBudgetAlreadyClosed)
async def monthly_budget_closed_handler(_request: Request, exc: MonthlyBudgetAlreadyClosed) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(MonthlyBudgetException)
async def monthly_budget_generic_handler(_request: Request, exc: MonthlyBudgetException) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(router, prefix="/api/v1")
app.include_router(monthly_budget_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health() -> Response:
    return Response(
        status_code=200, content='{"status":"healthy", "service":"budget-service"}', media_type="application/json"
    )
