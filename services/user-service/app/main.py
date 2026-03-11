from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import dependencies
from app.adapters.inbound.rest_api import router as users_router
from app.adapters.outbound.rabbitmq_publisher import RabbitMQPublisher
from app.config import settings
from app.domain.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    publisher = RabbitMQPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    dependencies._publisher = publisher
    logger.info("User-service started")
    yield
    await publisher.close()
    logger.info("User-service stopped")


app = FastAPI(
    title="User Service",
    version="0.1.0",
    lifespan=lifespan,
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
