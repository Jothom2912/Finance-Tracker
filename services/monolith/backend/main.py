import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

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
        correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
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
# Account routes removed — account-service owns this domain now (Phase 4 cutover)
# User/Goal REST routes removed — user-service (8001) and goal-service (8006) own these
from backend.analytics.adapters.inbound.graphql_api import create_graphql_router
from backend.analytics.adapters.inbound.rest_api import dashboard_router
# Banking routes owned by banking-service (port 8009) after extraction cutover.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.

    Skips the MySQL bootstrap when running under pytest — tests
    manage their own (in-memory) schema via fixtures, and the real
    MySQL isn't available.  Controlled by ``SKIP_DB_BOOTSTRAP`` or
    the presence of ``PYTEST_CURRENT_TEST`` in the environment.
    """
    logger.info("Starting FastAPI application...")
    import os

    if os.environ.get("SKIP_DB_BOOTSTRAP") or os.environ.get("PYTEST_CURRENT_TEST"):
        logger.info("Skipping DB bootstrap (test mode detected)")
    else:
        from backend.database.mysql import create_db_tables

        create_db_tables()

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

# Transaction and planned-transaction CRUD now owned by
# transaction-service (port 8002).  The monolith reads from the
# MySQL projection (see TransactionSyncConsumer) but never writes.

v1.include_router(dashboard_router)
v1.include_router(create_graphql_router(), prefix="/graphql")

app.include_router(v1)
