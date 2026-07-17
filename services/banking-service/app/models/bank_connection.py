from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_VALID_STATUSES = ("active", "inactive", "disconnected")


class BankConnectionModel(Base):
    __tablename__ = "bank_connections"

    id: Mapped[str] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_country: Mapped[str] = mapped_column(String(5), nullable=False, server_default="DK")
    bank_account_uid: Mapped[str] = mapped_column(String(200), nullable=False)
    bank_account_iban: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # In-flight sync-claim (P3-14): sat atomisk når en sync-saga startes,
    # ryddet ved mark_sync_complete; serialiserer sagas per connection.
    sync_saga_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sync_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"status IN {_VALID_STATUSES!r}",
            name="ck_bank_connection_status",
        ),
    )
