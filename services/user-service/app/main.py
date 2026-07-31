from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from observability import setup_logging

from app.adapters.inbound.rest_api import router as users_router
from app.config import settings
from app.domain.exceptions import (
    CurrentPasswordIncorrectException,
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="User Service",
    version="0.2.0",
    description="Handles user registration and authentication. "
    "Domain events are persisted via transactional outbox and "
    "published by a separate worker process.",
)


@app.exception_handler(UserAlreadyExistsException)
async def user_already_exists_handler(_request: Request, exc: UserAlreadyExistsException) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidCredentialsException)
async def invalid_credentials_handler(_request: Request, exc: InvalidCredentialsException) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(CurrentPasswordIncorrectException)
async def current_password_incorrect_handler(_request: Request, exc: CurrentPasswordIncorrectException) -> JSONResponse:
    # 403, ikke 401. En 401 herfra ville få frontendens apiClient til at
    # rydde sessionen og redirecte til /login — altså logge brugeren ud
    # fordi de tastede deres nuværende password forkert.
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(UserNotFoundException)
async def user_not_found_handler(_request: Request, exc: UserNotFoundException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


app.include_router(users_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "user-service"}
