from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.inbound.rest_api import router
from app.config import settings
from app.domain.exceptions import (
    AccountRequiredForBudget,
    BudgetNotFound,
    CategoryNotFoundForBudget,
    CategoryRequiredForBudget,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Budget Service", version="1.0.0")

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


app.include_router(router, prefix="/api/v1")
