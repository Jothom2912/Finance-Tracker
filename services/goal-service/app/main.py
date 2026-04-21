from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.inbound.goal_api import router as goal_router
from app.config import settings
from app.domain.exceptions import AccountNotFoundForGoal, GoalException

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Goal Service",
    version="0.1.0",
    description="Manages financial goals and savings targets.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GoalException)
async def goal_exception_handler(_request, exc: GoalException):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(AccountNotFoundForGoal)
async def account_not_found_handler(_request, exc: AccountNotFoundForGoal):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(goal_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "goal-service"}
