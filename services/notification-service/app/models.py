"""SQLAlchemy models for notification-service.

``sa.Uuid`` (dialect-agnostic) rather than the Postgres-only ``UUID`` type
so the same models run on aiosqlite in tests. The UUIDv7 default is applied
application-side (see :func:`app.domain.ids.uuid7`) because Postgres has no
native uuid7 before v18.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain.ids import uuid7


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Deterministic idempotency key — unique so redelivery / repeated
    # goal.updated events collapse onto one row.
    source_key: Mapped[str] = mapped_column(sa.String(200), nullable=False, unique=True)
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        # Feed listing + unread-count are always scoped to one user, newest first.
        sa.Index("ix_notifications_user_created", "user_id", "created_at"),
    )
