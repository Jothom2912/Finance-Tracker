import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.account_api import router as account_router
from app.adapters.inbound.account_group_api import router as account_group_router
from app.config import CORS_ORIGINS, DATABASE_URL

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run Alembic migrations to head on startup."""
    from alembic import command
    from alembic.config import Config

    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL or "")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception as exc:
        logger.error(f"Migration failed: {exc}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("TESTING"):
        _run_migrations()
    yield



app = FastAPI(
    title="Account Service",
    version="0.1.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router, prefix="/api/v1")
app.include_router(account_group_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "account-service"}