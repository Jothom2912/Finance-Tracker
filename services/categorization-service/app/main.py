from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.inbound.categorize_api import categorize_router
from app.adapters.inbound.category_api import category_router, subcategory_router
from app.config import settings
from app.domain.exceptions import (
    CategoryHasSubcategories,
    CategoryNotFound,
    DuplicateCategoryName,
    DuplicateSubCategoryName,
    InvalidCategoryType,
    SubCategoryInUse,
    SubCategoryNotFound,
)
from app.rule_engine_provider import RuleEngineProvider

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Categorization Service",
    version="0.1.0",
    description="Owns taxonomy (categories, subcategories, merchants), "
    "rule engine, and categorization pipeline. "
    "Exposes sync /categorize for tier 1 and async event-driven "
    "categorization for tier 2/3.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rule_engine_provider = RuleEngineProvider(ttl_seconds=60)


@app.on_event("startup")
async def startup_warmup() -> None:
    """Preload rule engine and warm DB pool to eliminate cold-start latency."""
    try:
        await rule_engine_provider.warmup()
        logger.info("Startup warmup complete")
    except Exception:
        logger.warning(
            "Startup warmup failed — rule engine will lazy-load on first request",
            exc_info=True,
        )


@app.exception_handler(CategoryNotFound)
async def category_not_found_handler(_request: Request, exc: CategoryNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(SubCategoryNotFound)
async def subcategory_not_found_handler(_request: Request, exc: SubCategoryNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DuplicateCategoryName)
async def duplicate_category_handler(_request: Request, exc: DuplicateCategoryName) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DuplicateSubCategoryName)
async def duplicate_subcategory_handler(
    _request: Request, exc: DuplicateSubCategoryName
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(CategoryHasSubcategories)
async def category_has_subcategories_handler(
    _request: Request, exc: CategoryHasSubcategories
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(SubCategoryInUse)
async def subcategory_in_use_handler(_request: Request, exc: SubCategoryInUse) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidCategoryType)
async def invalid_category_type_handler(
    _request: Request, exc: InvalidCategoryType
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.include_router(categorize_router)
app.include_router(category_router)
app.include_router(subcategory_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "categorization-service"}
