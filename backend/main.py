from contextlib import asynccontextmanager
import json
import logging
import time
import uuid

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import CORS_ORIGINS, ENVIRONMENT, LOG_LEVEL

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

_log_level = getattr(logging, LOG_LEVEL, logging.INFO)

if ENVIRONMENT == "development":
    logging.basicConfig(
        level=_log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
else:
    _json_handler = logging.StreamHandler()
    _json_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.basicConfig(level=_log_level, handlers=[_json_handler])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request logging middleware with correlation ID
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Adds a correlation ID to every request and logs method/path/status/duration."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get(
            "x-correlation-id", str(uuid.uuid4())
        )
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id

        log_data = {
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }

        if ENVIRONMENT == "development":
            logger.info(
                "%s %s -> %s (%.1fms) [%s]",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                correlation_id[:8],
            )
        else:
            logger.info(json.dumps(log_data))

        return response

# Hexagonal architecture routers
from backend.transaction.adapters.inbound.rest_api import (
    router as transaction_router,
    planned_router as planned_transaction_router,
)
from backend.category.adapters.inbound.rest_api import router as category_router
from backend.budget.adapters.inbound.rest_api import router as budget_router
from backend.account.adapters.inbound.account_api import router as account_router
from backend.account.adapters.inbound.account_group_api import router as account_group_router
from backend.goal.adapters.inbound.goal_api import router as goal_router
from backend.user.adapters.inbound.user_api import router as user_router
from backend.monthly_budget.adapters.inbound.rest_api import (
    router as monthly_budget_router,
)
from backend.analytics.adapters.inbound.rest_api import (
    dashboard_router,
    budget_summary_router,
)
from backend.analytics.adapters.inbound.graphql_api import create_graphql_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting FastAPI application...")
    yield
    logger.info("Stopping FastAPI application...")

app = FastAPI(title="Personlig Finans Tracker API", lifespan=lifespan)

# Middleware stack (order matters: last added runs first)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Velkommen til din Personlige Finans Tracker API!"}

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Backend kører!", "timestamp": time.time()}

# ---------------------------------------------------------------------------
# API v1 router -- all domain routes under /api/v1/
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/api/v1")

v1.include_router(transaction_router)
v1.include_router(planned_transaction_router)
v1.include_router(category_router)

# Budget summary MUST be included BEFORE CRUD to avoid
# /budgets/summary being matched by /budgets/{budget_id}
v1.include_router(budget_summary_router)
v1.include_router(budget_router)

v1.include_router(monthly_budget_router)

v1.include_router(account_router)
v1.include_router(account_group_router)
v1.include_router(goal_router)
v1.include_router(user_router)

v1.include_router(dashboard_router)
v1.include_router(create_graphql_router(), prefix="/graphql")

app.include_router(v1)
