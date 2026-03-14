from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.inbound.rest_api import router as users_router
from app.config import settings
from app.domain.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="User Service",
    version="0.2.0",
    description="Handles user registration and authentication. "
    "Domain events are persisted via transactional outbox and "
    "published by a separate worker process.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(UserAlreadyExistsException)
async def user_already_exists_handler(
    _request: Request, exc: UserAlreadyExistsException
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidCredentialsException)
async def invalid_credentials_handler(
    _request: Request, exc: InvalidCredentialsException
) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(UserNotFoundException)
async def user_not_found_handler(
    _request: Request, exc: UserNotFoundException
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


app.include_router(users_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "user-service"}
