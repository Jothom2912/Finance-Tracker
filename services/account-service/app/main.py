import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from observability import setup_logging

from app.adapters.inbound.account_api import router as account_router
from app.adapters.inbound.account_group_api import router as account_group_router
from app.adapters.inbound.internal_api import router as internal_router
from app.config import DATABASE_URL, LOG_LEVEL

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging(LOG_LEVEL)

logger = logging.getLogger(__name__)


def _reassert_logging() -> None:
    """Re-apply our logging configuration after Alembic replaced it.

    This service is the only one that runs migrations *inside* the API process; the other
    eight do it in ``CMD``, in a process that exits.  Alembic's ``env.py`` calls
    ``fileConfig``, which does two things beyond disabling loggers: it **replaces** root's
    handler with ``alembic.ini``'s (``%(levelname)-5.5s [%(name)s]`` — no timestamp) and sets
    root's level to ``WARN``.  ``disable_existing_loggers=False`` (P3-58) does not prevent
    either.

    Without this call the fix looks delivered and is undone in exactly one service: measured
    on the running container, everything after the migration lost its timestamp and the
    ``logger.info`` below vanished from the log entirely.  P3-17 removes the need for this by
    taking migrations out of the API process.
    """
    setup_logging(LOG_LEVEL)


def _run_migrations() -> None:
    """Run Alembic migrations to head on startup."""
    from alembic import command
    from alembic.config import Config

    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL or "")
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        _reassert_logging()
        logger.error(f"Migration failed: {exc}")
        raise
    _reassert_logging()
    logger.info("Database migrations applied successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("TESTING"):
        _run_migrations()
    yield


app = FastAPI(title="Account Service", version="0.1.0", lifespan=lifespan)


app.include_router(account_router, prefix="/api/v1")
app.include_router(account_group_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "account-service"}
