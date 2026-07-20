from __future__ import annotations

from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from app.application.dto import (
    MarkAllReadResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.application.ports.outbound import IUnitOfWork
from app.auth import get_current_user_id
from app.config import settings
from app.dependencies import get_uow

app = FastAPI(title="Notification Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        raise HTTPException(status_code=404, detail="Notification not found")
    await uow.commit()
    return Response(status_code=204)
