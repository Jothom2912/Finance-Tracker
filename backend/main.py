from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import time

from backend.config import CORS_ORIGINS

# Konfigurer logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
from backend.analytics.adapters.inbound.rest_api import (
    dashboard_router,
    budget_summary_router,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting FastAPI application...")
    yield
    logger.info("Stopping FastAPI application...")

app = FastAPI(title="Personlig Finans Tracker API", lifespan=lifespan)

# CORS middleware (must be first middleware)
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

# Include hexagonal architecture routers
app.include_router(transaction_router)
app.include_router(planned_transaction_router)
app.include_router(category_router)

# Budget summary MUST be included BEFORE hexagonal CRUD
# to avoid /budgets/summary being matched by /budgets/{budget_id}
app.include_router(budget_summary_router)
app.include_router(budget_router)  # Hexagonal CRUD

# Include hexagonal account, goal, and user routers
app.include_router(account_router)
app.include_router(account_group_router)
app.include_router(goal_router)
app.include_router(user_router)

# Include hexagonal analytics routers
app.include_router(dashboard_router)
