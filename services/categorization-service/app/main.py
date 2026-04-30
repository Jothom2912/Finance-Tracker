from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.inbound.categorize_api import categorize_router
from app.config import settings
from app.domain.exceptions import (
    CategoryNotFound,
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


app.include_router(categorize_router)

# Category CRUD endpoints (category_router) are intentionally NOT registered.
# Transaction-service is the current authority for categories CRUD.
# Cat-service keeps a read copy via CategorySyncConsumer.
# See docs/ADR-002-categories-ownership-deferred.md.


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "categorization-service"}
