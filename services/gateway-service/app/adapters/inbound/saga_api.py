from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.outbound.saga_client import SagaServiceClient
from app.auth import get_user_id_from_headers

logger = logging.getLogger(__name__)

saga_router = APIRouter(prefix="/sagas", tags=["Sagas"])


@saga_router.get("/{saga_id}")
def get_saga_status_route(
    saga_id: str,
    user_id: int = Depends(get_user_id_from_headers),
) -> dict[str, Any]:
    client = SagaServiceClient()
    try:
        saga = client.get_saga_status(saga_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saga not found",
            ) from exc
        logger.exception("Saga service returned HTTP %s for saga=%s", exc.response.status_code, saga_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Saga service unavailable",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Saga service unreachable for saga=%s", saga_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Saga service unavailable",
        ) from exc

    saga_user_id = saga.get("context", {}).get("user_id")
    if saga_user_id is None or int(saga_user_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return saga
