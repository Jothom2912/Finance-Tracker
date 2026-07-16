from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProcessedEventModel(Base):
    __tablename__ = "processed_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("correlation_id", "consumer_name", name="uq_processed_event"),)
