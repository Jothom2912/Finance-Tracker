from __future__ import annotations

from datetime import datetime

from messaging import OutboxEventMixin
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Nullable: NULL betyder "aldrig ændret siden oprettelsen" (F2-08,
    # migration 003). Sættes eksplicit af repositoryets update_*-metoder.
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)


class OutboxEventModel(OutboxEventMixin, Base):
    """Service-owned outbox table; columns come from the shared mixin.

    Kept as a thin local class so Alembic metadata stays service-owned
    (columns and ``ix_outbox_pending_poll`` match migration 002 exactly).
    """
