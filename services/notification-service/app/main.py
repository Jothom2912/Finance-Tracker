from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from observability import setup_logging

from app.application.dto import (
    MarkAllReadResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.application.ports.outbound import IUnitOfWork
from app.auth import get_current_user_id
from app.dependencies import get_uow

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging()

# P3-59: servicens fire eksisterende warnings ligger alle i consumer-processen. API'et
# havde ingen, og det er den første her.
logger = logging.getLogger(__name__)

app = FastAPI(title="Notification Service", version="0.1.0")


def _log_no_row_matched(operation: str, notification_id: UUID, user_id: int) -> None:
    """Log en 404 fra en skrivesti — og vær ærlig om at vi ikke ved hvorfor.

    P3-59: ejerskabstjekket ligger i `WHERE`-klausulen
    (`postgres_notification_repository.py:100-108`, `:128-136`), så `rowcount == 0` dækker
    **tre** tilstande: notifikationen findes ikke, den findes men tilhører en anden, eller
    den er allerede afvist. Klienten får samme 404 i alle tre.

    At skelne dem koster en ekstra `SELECT` pr. afvisning, og det er bevidst **ikke** betalt:
    de tre kræver ikke forskellige handlinger fra os. Men så skal linjen heller ikke lade
    som om den ved hvilken af dem det var. En loglinje der lyver om sin egen præcision er
    værre end en der siger at den ikke ved det — den får den næste debugger til at udelukke
    de to andre muligheder på et falsk grundlag.
    """
    logger.warning(
        "Ingen række matchede ved %s: bruger %s, notifikation %s "
        "— findes ikke, tilhører en anden, eller er allerede afvist",
        operation,
        user_id,
        notification_id,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "notification-service"}


@app.get("/api/v1/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    unread: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    uow: IUnitOfWork = Depends(get_uow),
) -> list[NotificationResponse]:
    rows = await uow.notifications.list_for_user(user_id, unread_only=unread, limit=limit, offset=offset)
    return [NotificationResponse.from_entity(n) for n in rows]


@app.get("/api/v1/notifications/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user_id: int = Depends(get_current_user_id),
    uow: IUnitOfWork = Depends(get_uow),
) -> UnreadCountResponse:
    return UnreadCountResponse(count=await uow.notifications.unread_count(user_id))


@app.post("/api/v1/notifications/read-all", response_model=MarkAllReadResponse)
async def mark_all_read(
    user_id: int = Depends(get_current_user_id),
    uow: IUnitOfWork = Depends(get_uow),
) -> MarkAllReadResponse:
    updated = await uow.notifications.mark_all_read(user_id)
    await uow.commit()
    return MarkAllReadResponse(updated=updated)


@app.post("/api/v1/notifications/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: UUID,
    user_id: int = Depends(get_current_user_id),
    uow: IUnitOfWork = Depends(get_uow),
) -> Response:
    matched = await uow.notifications.mark_read(notification_id, user_id)
    if not matched:
        _log_no_row_matched("markér-læst", notification_id, user_id)
        raise HTTPException(status_code=404, detail="Notification not found")
    await uow.commit()
    return Response(status_code=204)


@app.delete("/api/v1/notifications/{notification_id}", status_code=204)
async def dismiss(
    notification_id: UUID,
    user_id: int = Depends(get_current_user_id),
    uow: IUnitOfWork = Depends(get_uow),
) -> Response:
    matched = await uow.notifications.dismiss(notification_id, user_id)
    if not matched:
        _log_no_row_matched("afvisning", notification_id, user_id)
        raise HTTPException(status_code=404, detail="Notification not found")
    await uow.commit()
    return Response(status_code=204)
