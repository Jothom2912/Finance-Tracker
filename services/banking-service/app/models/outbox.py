from __future__ import annotations

from messaging import OutboxEventMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OutboxEventModel(OutboxEventMixin, Base):
    """Service-owned outbox table; columns come from the shared mixin.

    ``correlation_id`` is redeclared wider (255) than the mixin default (36)
    to match this service's migration.
    """

    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
