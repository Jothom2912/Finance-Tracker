from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from messaging import OutboxEventMixin
from sqlalchemy import Boolean, Date, Index, Integer, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CategoryModel(Base):
    """Event-synced read copy of categorization-service's categories.

    Per ADR-003 this service no longer owns categories; the copy exists
    for name denormalization on transactions. Ordering (display_order)
    is a presentation concern served by categorization-service and is
    deliberately not projected here.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(45), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class SubCategoryModel(Base):
    """Event-synced read copy of categorization-service's subcategories.

    Used to resolve ``subcategory_name`` on write paths and to validate
    that a manually chosen subcategory belongs to the chosen category —
    without an HTTP call to categorization-service. See ADR-003 and
    migration 010.
    """

    __tablename__ = "subcategories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TransactionModel(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Source-system identity for bank-imported rows (Enable Banking
    # entry_reference); NULL for manual/CSV rows.  Currency is implicitly
    # DKK everywhere until F3-03 — the server default keeps the manual
    # insert path unchanged.  See migration 012.
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="DKK")
    # Categorization pipeline metadata (nullable; populated by the
    # banking module's rule engine today, future ML/LLM adapters
    # tomorrow).  See migration 004_add_categorization_metadata.
    subcategory_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Denormalized subcategory name for display.  category_name is ALWAYS the
    # parent-level name; subcategory_name carries the sub-level name (e.g.
    # category_name="Mad & drikke", subcategory_name="Dagligvarer").  See
    # migration 009 and the category-consistency work (Fase 2).
    subcategory_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categorization_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    categorization_confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())

    __table_args__ = (
        # Serves the batch anti-join on the import dedup key
        # (user_id, account_id, date, amount, description) — migration 011.
        # Non-unique on purpose: identical keys are legitimate outside
        # the import paths (see the migration docstring).
        Index(
            "ix_transactions_dedup_key",
            "user_id",
            "account_id",
            "date",
            "amount",
            "description",
        ),
        # Idempotency key for bank imports — unique only where an
        # external_id exists, so manual/CSV duplicates stay legal.
        # Doubles as the concurrent-saga backstop (migration 012).
        Index(
            "uq_transactions_account_external_id",
            "account_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )


class PlannedTransactionModel(Base):
    __tablename__ = "planned_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False)
    next_execution: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class OutboxEventModel(OutboxEventMixin, Base):
    """Service-owned outbox table; columns come from the shared mixin.

    Kept as a thin local class so Alembic metadata stays service-owned
    (columns and ``ix_outbox_pending_poll`` match the outbox migration exactly).
    """


class ProcessedEventModel(Base):
    """Inbox pattern — deduplication for consumed events.

    ``message_id`` maps to ``BaseEvent.correlation_id`` (per-event UUID).
    See categorization-service docs/SCHEMA.md for naming rationale.
    """

    __tablename__ = "processed_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("uq_processed_events", "message_id", "consumer_name", unique=True),
        Index("ix_processed_at", "processed_at"),
    )
