from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PendingAuthorizationModel(Base):
    __tablename__ = "pending_authorizations"

    id: Mapped[str] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    state: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
