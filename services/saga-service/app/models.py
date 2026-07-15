from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from messaging import OutboxEventMixin
from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SagaInstanceModel(Base):
    __tablename__ = "saga_instances"

    id: Mapped[str] = mapped_column(sa.Uuid(as_uuid=False), primary_key=True)
    saga_type: Mapped[str] = mapped_column(String(100), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_saga_instances_active",
            "status",
            postgresql_where=sa.text("status IN ('started', 'compensating')"),
        ),
    )


class SagaStepLogModel(Base):
    __tablename__ = "saga_step_log"

    id: Mapped[str] = mapped_column(sa.Uuid(as_uuid=False), primary_key=True)
    saga_id: Mapped[str] = mapped_column(sa.Uuid(as_uuid=False), sa.ForeignKey("saga_instances.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    command_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compensated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (sa.UniqueConstraint("saga_id", "step_index", name="uq_saga_step_log_saga_step"),)


class OutboxEventModel(OutboxEventMixin, Base):
    """Service-owned outbox table; columns come from the shared mixin.

    ``correlation_id`` is redeclared wider (200) than the mixin default (36)
    to match this service's migration.
    """

    correlation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
